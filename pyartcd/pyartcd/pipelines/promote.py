import asyncio
import functools
import json
import logging
import os
import re
import sys
import traceback
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import aiohttp
import click
import semver
from doozerlib import assembly
from doozerlib.util import brew_arch_for_go_arch, brew_suffix_for_arch
from pyartcd import constants, exectools, util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.exceptions import VerificationError
from pyartcd.runtime import Runtime
from semver import VersionInfo
from tenacity import (RetryError, before_sleep_log, retry,
                      retry_if_exception_type, retry_if_result,
                      stop_after_attempt, wait_fixed)


class PromotePipeline:
    DEST_RELEASE_IMAGE_REPO = constants.RELEASE_IMAGE_REPO

    def __init__(self, runtime: Runtime, group: str, assembly: str, release_offset: Optional[int],
                 arches: Iterable[str], skip_blocker_bug_check: bool = False, skip_attached_bug_check: bool = False,
                 skip_image_list: bool = False, permit_overwrite: bool = False) -> None:
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.release_offset = release_offset
        self.arches = list(arches)
        self.skip_blocker_bug_check = skip_blocker_bug_check
        self.skip_attached_bug_check = skip_attached_bug_check
        self.skip_image_list = skip_image_list
        self.permit_overwrite = permit_overwrite

        self._logger = self.runtime.logger
        self._slack_client = self.runtime.new_slack_client()
        self._mail = self.runtime.new_mail_client()

        self._working_dir = self.runtime.working_dir
        self._doozer_working_dir = self._working_dir / "doozer-working"
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._doozer_working_dir)
        self._doozer_lock = asyncio.Lock()
        self._elliott_working_dir = self._working_dir / "elliott-working"
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self._elliott_working_dir)
        self._elliott_lock = asyncio.Lock()
        self._ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        if self._ocp_build_data_url:
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = self._ocp_build_data_url
            self._doozer_env_vars["DOOZER_DATA_PATH"] = self._ocp_build_data_url

    async def run(self):
        logger = self.runtime.logger

        # Load group config and releases.yml
        logger.info("Loading build data...")
        group_config = await util.load_group_config(self.group, self.assembly, env=self._doozer_env_vars)
        releases_config = await util.load_releases_config(self._doozer_working_dir / "ocp-build-data")
        if releases_config.get("releases", {}).get(self.assembly) is None:
            raise ValueError(f"To promote this release, assembly {self.assembly} must be explictly defined in releases.yml.")
        permits = util.get_assembly_promotion_permits(releases_config, self.assembly)

        # Get release name
        assembly_type = util.get_assembly_type(releases_config, self.assembly)
        release_name = util.get_release_name(assembly_type, self.group, self.assembly, self.release_offset)
        # Ensure release name is valid
        if not VersionInfo.isvalid(release_name):
            raise ValueError(f"Release name `{release_name}` is not a valid semver.")
        logger.info("Release name: %s", release_name)

        self._slack_client.bind_channel(release_name)
        slack_response = await self._slack_client.say(f"Promoting release `{release_name}`")
        slack_thread = slack_response["message"]["ts"]

        justifications = []
        try:
            # Get arches
            arches = self.arches or group_config.get("arches", [])
            arches = list(set(map(brew_arch_for_go_arch, arches)))
            if not arches:
                raise ValueError("No arches specified.")
            # Get previous list
            upgrades_str: Optional[str] = group_config.get("upgrades")
            if upgrades_str is None and assembly_type != assembly.AssemblyTypes.CUSTOM:
                raise ValueError(f"Group config for assembly {self.assembly} is missing the required `upgrades` field. If no upgrade edges are expected, please explicitly set the `upgrade` field to empty string.")
            previous_list = list(map(lambda s: s.strip(), upgrades_str.split(","))) if upgrades_str else []
            # Ensure all versions in previous list are valid semvers.
            if any(map(lambda version: not VersionInfo.isvalid(version), previous_list)):
                raise ValueError("Previous list (`upgrades` field in group config) has an invalid semver.")

            # Check for blocker bugs
            if self.skip_blocker_bug_check or assembly_type in [assembly.AssemblyTypes.CANDIDATE, assembly.AssemblyTypes.CUSTOM]:
                logger.info("Blocker Bug check is skipped.")
            else:
                logger.info("Checking for blocker bugs...")
                # TODO: Needs an option in releases.yml to skip this check
                try:
                    await self.check_blocker_bugs()
                except VerificationError as err:
                    logger.warn("Blocker bugs found for release; do not proceed without resolving; see https://github.com/openshift-eng/art-docs/blob/master/release/4.y.z-stream.md#handling-blocker-bugs: %s", err)
                    justification = self._reraise_if_not_permitted(err, "BLOCKER_BUGS", permits)
                    justifications.append(justification)
                logger.info("No blocker bugs found.")

            # If there are CVEs, convert RHBAs to RHSAs and attach CVE flaw bugs
            impetus_advisories = group_config.get("advisories", {})
            futures = []
            for impetus, advisory in impetus_advisories.items():
                if not advisory:
                    continue
                if advisory < 0:  # placeholder advisory id is still in group config?
                    raise ValueError("Found invalid %s advisory %s", impetus, advisory)
                logger.info("Attaching CVE flaws for %s advisory %s...", impetus, advisory)
                futures.append(self.attach_cve_flaws(advisory))
            try:
                await asyncio.gather(*futures)
            except ChildProcessError as err:
                logger.warn("Error attaching CVE flaw bugs: %s", err)
                justification = self._reraise_if_not_permitted(err, "CVE_FLAWS", permits)
                justifications.append(justification)

            # Ensure the image advisory is in QE (or later) state.
            # TODO: We may need an option to permit all advisories states
            image_advisory = impetus_advisories.get("image", 0)
            errata_url = ""

            if assembly_type == assembly.AssemblyTypes.STANDARD:
                if image_advisory <= 0:
                    err = VerificationError(f"No associated image advisory for {self.assembly} is defined.")
                    self._raise_if_not_waived(err, "NO_ERRATA", permits)
                    logger.warning("%s", err)
                else:
                    logger.info("Verifying associated image advisory %s...", image_advisory)
                    image_advisory_info = await self.get_advisory_info(image_advisory)
                    try:
                        self.verify_image_advisory(image_advisory_info)
                        live_id = self.get_live_id(image_advisory_info)
                        assert live_id
                        errata_url = f"https://access.redhat.com/errata/{live_id}"  # don't quote
                    except VerificationError as err:
                        logger.warning("%s", err)
                        justification = self._raise_if_not_waived(err, "INVALID_ERRATA_STATUS", permits)
                        justifications.append(justification)

            # Verify attached bugs
            advisories = list(filter(lambda ad: ad > 0, impetus_advisories.values()))
            if advisories:
                if self.skip_attached_bug_check:
                    logger.info("Skip checking attached bugs.")
                else:
                    logger.info("Verifying attached bugs...")
                    try:
                        await self.verify_attached_bugs(advisories)
                    except ChildProcessError as err:
                        logger.warn("Error verifying attached bugs: %s", err)
                        justification = self._reraise_if_not_permitted(err, "ATTACHED_BUGS", permits)
                        justifications.append(justification)

            # Promote release images
            futures = []
            metadata = {}
            description = group_config.get("description")
            if description:
                logger.warning("The following description message will be included in the metadata of release image: %s", description)
                metadata["description"] = str(description)
            if errata_url:
                metadata["url"] = errata_url
            reference_releases = util.get_assmebly_basis(releases_config, self.assembly).get("reference_releases", {})
            tag_stable = assembly_type in [assembly.AssemblyTypes.STANDARD, assembly.AssemblyTypes.CANDIDATE]
            release_infos = await self.promote_all_arches(release_name, arches, previous_list, metadata, reference_releases, tag_stable)
            self._logger.info("All release images for %s have been promoted.", release_name)

            # Wait for release controllers
            pullspecs = list(map(lambda r: r["image"], release_infos))
            if not tag_stable:
                self._logger.warning("This release will not appear on release controllers. Pullspecs: %s", release_name, ", ".join(pullspecs))
                await self._slack_client.say(f"Hi @release-artists. Release {release_name} is ready. It will not appear on the release controllers. Please tell the user to manually pull the release images: {', '.join(pullspecs)}", slack_thread)
            else:  # Wait for release images to be accepted by the release controllers
                self._logger.info("All release images for %s have been successfully promoted. Pullspecs: %s", release_name, ", ".join(pullspecs))

                self._logger.info("Determining upgrade tests...")
                test_commands = self._get_upgrade_tests_commands(release_name, previous_list)
                message = f"""Hi @release-artists . A new release `{release_name}` is ready and needs some upgrade tests to be triggered.
Please open a chat with @cluster-bot and issue each of these lines individually:
{os.linesep.join(test_commands)}
"""
                await self._slack_client.say(message, slack_thread)

                self._logger.info("Waiting for release images for %s to be accepted by the release controller...", release_name)
                futures = []
                for arch in arches:
                    go_arch_suffix = util.go_suffix_for_arch(arch)
                    release_stream = f"4-stable{go_arch_suffix}"
                    futures.append(self.wait_for_stable(release_name, arch, release_stream))
                try:
                    await asyncio.gather(*futures)
                except RetryError as err:
                    message = f"Timeout waiting for release to be accepted by the release controllers: {err}"
                    self._logger.error(message)
                    self._logger.exception(err)
                    raise TimeoutError(message)

                self._logger.info("All release images for %s have been accepted by the release controllers.", release_name)

                message = f"Hi @release-artists . Release `{release_name}` has been accepted by the release controllers."
                await self._slack_client.say(message, slack_thread)

                # Send image list
                if not image_advisory:
                    self._logger.warning("No need to send an advisory image list because this release doesn't have an image advisory.")
                elif assembly_type == assembly.AssemblyTypes.CANDIDATE:
                    self._logger.warning("No need to send an advisory image list for a candidate release.")
                elif self.skip_image_list:
                    self._logger.warning("Skip sending advisory image list")
                else:
                    self._logger.info("Gathering and sending advisory image list...")
                    mail_dir = self._working_dir / "email"
                    await self.send_image_list_email(release_name, image_advisory, mail_dir)
                    self._logger.info("Advisory image list sent.")

        except Exception as err:
            self._logger.exception(err)
            error_message = f"Error promoting release {release_name}: {err}\n {traceback.format_exc()}"
            message = f"Hi @release-artists . Promoting release {release_name} failed with: {error_message}"
            await self._slack_client.say(message, slack_thread)
            raise

        # Print release infos to console
        data = {
            "group": self.group,
            "assembly": self.assembly,
            "type": assembly_type.value,
            "name": release_name,
            "content": {},
            "justifications": justifications,
        }
        if errata_url:
            data["advisory"] = image_advisory
            data["live_url"] = errata_url
        for arch, release_info in zip(arches, release_infos):
            data["content"][arch] = {
                "pullspec": release_info["image"],
                "digest": release_info["digest"],
            }
            from_release = release_info.get("references", {}).get("metadata", {}).get("annotations", {}).get("release.openshift.io/from-release")
            if from_release:
                data["content"][arch]["from_release"] = from_release
            rhcos = next((t for t in release_info.get("references", {}).get("spec", {}).get("tags", []) if t["name"] == "machine-os-content"), None)
            if rhcos:
                rhcos_version = rhcos["annotations"]["io.openshift.build.versions"].split("=")[1]  # machine-os=48.84.202112162302-0 => 48.84.202112162302-0
                data["content"][arch]["rhcos_version"] = rhcos_version

        json.dump(data, sys.stdout)

    def _reraise_if_not_permitted(self, err: VerificationError, code: str, permits: Iterable[Dict]):
        permit = next(filter(lambda waiver: waiver["code"] == code, permits), None)
        if not permit:
            raise err
        justification: Optional[str] = permit.get("why")
        if not justification:
            raise ValueError("A justification is required to permit issue %s.", code)
        self.logger.warn("Issue %s is permitted with justification: %s", err, justification)
        return justification

    async def check_blocker_bugs(self):
        # Note: --assembly option should always be "stream". We are checking blocker bugs for this release branch regardless of the sweep cutoff timestamp.
        cmd = [
            "elliott",
            f"--group={self.group}",
            "--assembly=stream",
            "find-bugs",
            "--mode=blocker",
            "--report"
        ]
        async with self._elliott_lock:
            _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, stderr=None)
        match = re.search(r"Found ([0-9]+) bugs", stdout)
        if not match:
            raise IOError(f"Could determine whether this release has blocker bugs. Elliott printed unexpected message: {stdout}")
        if int(match[1]) != 0:
            raise VerificationError(f"{int(match[1])} blocker Bug(s) found for release; do not proceed without resolving. See https://github.com/openshift-eng/art-docs/blob/master/release/4.y.z-stream.md#handling-blocker-bugs")

    async def attach_cve_flaws(self, advisory: int):
        # raise ChildProcessError("test")
        cmd = [
            "elliott",
            f"--group={self.group}",
            "attach-cve-flaws",
            f"--advisory={advisory}",
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")
        async with self._elliott_lock:
            await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, stdout=sys.stderr)

    async def get_advisory_info(self, advisory: int) -> Dict:
        cmd = [
            "elliott",
            f"--group={self.group}",
            "get",
            "--json", "-",
            "--", f"{advisory}"
        ]
        async with self._elliott_lock:
            _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, stderr=None)
        advisory_info = json.loads(stdout)
        if not isinstance(advisory_info, dict):
            raise ValueError(f"Got invalid advisory info for advisory {advisory}: {advisory_info}.")
        return advisory_info

    @staticmethod
    def get_live_id(advisory_info: Dict):
        # Extract live ID from advisory info
        # Examples:
        # - advisory with a live ID
        #     "errata_id": 2681,
        #     "fulladvisory": "RHBA-2019:2681-02",
        #     "id": 46049,
        #     "old_advisory": "RHBA-2019:46049-02",
        # - advisory without a live ID
        #     "errata_id": 46143,
        #     "fulladvisory": "RHBA-2019:46143-01",
        #     "id": 46143,
        #     "old_advisory": null,
        if advisory_info["errata_id"] == advisory_info["id"]:
            # advisory doesn't have a live ID
            return None
        live_id = advisory_info["fulladvisory"].rsplit("-", 1)[0]  # RHBA-2019:2681-02 => RHBA-2019:2681
        return live_id

    def verify_image_advisory(self, advisory_info: Dict):
        issues = []
        live_id = self.get_live_id(advisory_info)
        if not live_id:
            issues.append(f"Advisory {advisory_info['id']} doesn't have a live ID.")
        if advisory_info["status"] not in {"QE", "REL_PREP", "PUSH_READY", "IN_PUSH", "SHIPPED_LIVE"}:
            issues.append(f"Advisory {advisory_info['id']} cannot be in {advisory_info['status']} state.")
        if issues:
            raise VerificationError(f"Advisory {advisory_info['id']} has the following issues:\n" + '\n'.join(issues))

    async def verify_attached_bugs(self, advisories: Iterable[int]):
        advisories = list(advisories)
        if not advisories:
            self._logger.warning("No advisories to verify.")
            return
        cmd = [
            "elliott",
            f"--group={self.group}",
            "verify-attached-bugs",
            "--"
        ]
        for advisory in advisories:
            cmd.append(f"{advisory}")
        async with self._elliott_lock:
            await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, stdout=sys.stderr)

    async def promote_all_arches(self, release_name: str, arches: List[str], previous_list: List[str], metadata: Optional[Dict], reference_releases: Dict[str, str], tag_stable: bool):
        futures = []
        for arch in arches:
            futures.append(self.promote_arch(release_name, arch, previous_list, metadata, reference_releases.get(arch), tag_stable))
        try:
            release_infos = await asyncio.gather(*futures)
        except ChildProcessError as err:
            self._logger.error("Error promoting release images: %s\n%s", str(err), traceback.format_exc())
            raise
        return release_infos

    async def promote_arch(self, release_name: str, arch: str, previous_list: List[str], metadata: Optional[Dict], reference_release: Optional[str], tag_stable: bool):
        brew_arch = util.brew_arch_for_go_arch(arch)  # ensure we are using Brew arches (e.g. aarch64) instead of golang arches (e.g. arm64).
        dest_image_tag = f"{release_name}-{brew_arch}"
        dest_image_pullspec = f"{self.DEST_RELEASE_IMAGE_REPO}:{dest_image_tag}"
        self._logger.info("Checking if release image %s for %s (%s) already exists...", release_name, arch, dest_image_pullspec)
        dest_image_info = await self.get_release_image_info(dest_image_pullspec)
        if dest_image_info:  # this arch-specific release image is already promoted
            self._logger.warning("Release image %s for %s (%s) already exists", release_name, arch, dest_image_info["image"])
            # TODO: Check if the existing release image matches the assembly definition.

        if not dest_image_info or self.permit_overwrite:
            if dest_image_info:
                self._logger.warning("The existing release image %s will be overwritten!", dest_image_pullspec)
            self._logger.info("Building arch-specific release image %s for %s (%s)...", release_name, arch, dest_image_pullspec)
            await self.build_release_image(release_name, brew_arch, previous_list, metadata, dest_image_pullspec, reference_release)
            self._logger.info("Release image for %s %s has been built and pushed to %s", release_name, arch, dest_image_pullspec)
            self._logger.info("Getting release image information for %s...", dest_image_pullspec)
            if not self.runtime.dry_run:
                dest_image_info = await self.get_release_image_info(dest_image_pullspec, raise_if_not_found=True)
            else:
                # populate fake data for dry run
                dest_image_info = {
                    "image": f"example.com/fake-release:{release_name}{brew_suffix_for_arch(arch)}",
                    "digest": f"fake:deadbeef{brew_suffix_for_arch(arch)}",
                    "references": {
                        "spec": {
                            "tags": [
                                {
                                    "name": "machine-os-content",
                                    "annotations": {"io.openshift.build.versions": "machine-os=00.00.212301010000-0"}
                                }
                            ]
                        }
                    }
                }
                if reference_release:
                    dest_image_info["references"]["metadata"] = {"annotations": {"release.openshift.io/from-release": reference_release}}
                else:
                    major, minor = util.isolate_major_minor_in_group(self.group)
                    go_arch_suffix = util.go_suffix_for_arch(arch, is_private=False)
                    dest_image_info["references"]["metadata"] = {"annotations": {"release.openshift.io/from-image-stream": f"fake{go_arch_suffix}/{major}.{minor}-art-assembly-{self.assembly}{go_arch_suffix}"}}

        if not tag_stable:
            self._logger.info("Release image %s will not appear on the release controller.", dest_image_pullspec)
            return dest_image_info

        go_arch_suffix = util.go_suffix_for_arch(arch)
        namespace = f"ocp{go_arch_suffix}"
        image_stream_tag = f"release{go_arch_suffix}:{release_name}"
        namespace_image_stream_tag = f"{namespace}/{image_stream_tag}"
        self._logger.info("Checking if ImageStreamTag %s exists...", namespace_image_stream_tag)
        ist = await self.get_image_stream_tag(namespace, image_stream_tag)
        if ist:
            ist_digest = ist["image"]["dockerImageReference"].split("@")[-1]
            if ist_digest == dest_image_info["digest"]:
                self._logger.info("ImageStreamTag %s already exists with digest %s matching release image %s.", namespace_image_stream_tag, ist_digest, dest_image_pullspec)
                return dest_image_info
            message = f"ImageStreamTag {namespace_image_stream_tag} already exists, but it has a different digest ({ist_digest}) from the expected release image {dest_image_pullspec} ({dest_image_info['digest']})."
            if not self.permit_overwrite:
                raise ValueError(message)
            self._logger.warning(message)
        else:
            self._logger.info("ImageStreamTag %s doesn't exist.", namespace_image_stream_tag)

        self._logger.info("Tagging release image %s into %s...", dest_image_pullspec, namespace_image_stream_tag)
        await self.tag_release(dest_image_pullspec, namespace_image_stream_tag)
        self._logger.info("Release image %s has been tagged into %s.", dest_image_pullspec, namespace_image_stream_tag)
        return dest_image_info

    @staticmethod
    async def get_release_image_info(pullspec: str, raise_if_not_found: bool = False):
        cmd = ["oc", "adm", "release", "info", "-o", "json", "--", pullspec]
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        rc, stdout, stderr = await exectools.cmd_gather_async(cmd, check=False, env=env)
        if rc != 0:
            if "not found: manifest unknown" in stderr:
                # release image doesn't exist
                if raise_if_not_found:
                    raise IOError(f"Image {pullspec} is not found.")
                return None
            raise ChildProcessError(f"Error running {cmd}: exit_code={rc}, stdout={stdout}, stderr={stderr}")
        info = json.loads(stdout)
        if not isinstance(info, dict):
            raise ValueError(f"Invalid release info: {info}")
        return info

    @staticmethod
    def _get_upgrade_tests_commands(release_name: str, previous_list: List[str]):
        previous_list = sorted(previous_list, key=functools.cmp_to_key(semver.compare), reverse=True)
        versions_by_minor: OrderedDict = OrderedDict()
        for version_str in previous_list:
            version = VersionInfo.parse(version_str)
            minor_version = f"{version.major}.{version.minor}"
            versions_by_minor.setdefault(minor_version, []).append(str(version))

        test_edges = []
        for _, versions in versions_by_minor.items():
            if len(versions) <= 15:
                test_edges.extend(versions)
                continue
            test_edges.extend(versions[:5])  # add first 5
            # 5 equally distributed between versions[5:-5]
            step = (len(versions) - 10) // 5
            test_edges.extend(versions[5:-5][step::step])
            test_edges.extend(versions[-5:])  # add last 5

        test_commands = []
        platforms = ['aws', 'gcp', 'azure']
        for edge in test_edges:
            platform = platforms[len(test_commands) % len(platforms)]
            test_commands.append(f"test upgrade {edge} {release_name} {platform}")
        return test_commands

    async def build_release_image(self, release_name: str, arch: str, previous_list: List[str], metadata: Optional[Dict], dest_image_pullspec: str, reference_release: Optional[str]):
        go_arch_suffix = util.go_suffix_for_arch(arch, is_private=False)
        cmd = [
            "oc",
            "adm",
            "release",
            "new",
            "-n",
            f"ocp{go_arch_suffix}",
            f"--name={release_name}",
            f"--to-image={dest_image_pullspec}",
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")
        if reference_release:
            cmd.append(f"--from-release=registry.ci.openshift.org/ocp{go_arch_suffix}/release{go_arch_suffix}:{reference_release}")
        else:
            major, minor = util.isolate_major_minor_in_group(self.group)
            src_image_stream = f"{major}.{minor}-art-assembly-{self.assembly}{go_arch_suffix}"
            cmd.extend(["--reference-mode=source", f"--from-image-stream={src_image_stream}"])

        if previous_list:
            cmd.append(f"--previous={','.join(previous_list)}")
        if metadata:
            cmd.append("--metadata")
            cmd.append(json.dumps(metadata))
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        await exectools.cmd_assert_async(cmd, env=env, stdout=sys.stderr)

    async def get_image_stream_tag(self, namespace: str, image_stream_tag: str):
        cmd = [
            "oc",
            "-n",
            namespace,
            "get",
            "imagestreamtag",
            "-o",
            "json",
            "--ignore-not-found",
            "--",
            image_stream_tag,
        ]
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        _, stdout, _ = await exectools.cmd_gather_async(cmd, env=env, stderr=None)
        stdout = stdout.strip()
        if not stdout:  # Not found
            return None
        return json.loads(stdout)

    async def tag_release(self, image_pullspec: str, image_stream_tag: str):
        cmd = [
            "oc",
            "tag",
            "--",
            image_pullspec,
            image_stream_tag,
        ]
        if self.runtime.dry_run:
            self._logger.warning("[DRY RUN] Would have run %s", cmd)
            return
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        await exectools.cmd_assert_async(cmd, env=env, stdout=sys.stderr)

    async def wait_for_stable(self, release_name: str, arch: str, release_stream: str):
        go_arch = util.go_arch_for_brew_arch(arch)
        release_controller_url = f"https://{go_arch}.ocp.releases.ci.openshift.org"
        if self.runtime.dry_run:
            actual_phase = await self.get_release_phase(release_controller_url, release_stream, release_name)
            self._logger.warning("[DRY RUN] Release %s for %s has phase %s. Assume accepted.", release_name, arch, actual_phase)
            return
        return await retry(
            stop=(stop_after_attempt(36)),  # wait for 5m * 36 = 180m = 3 hours
            wait=wait_fixed(300),  # wait for 5 minutes between retries
            retry=(retry_if_result(lambda phase: phase != "Accepted") | retry_if_exception_type()),
            before_sleep=before_sleep_log(self._logger, logging.WARNING),
        )(self.get_release_phase)(release_controller_url, release_stream, release_name)

    @staticmethod
    async def get_release_phase(release_controller_url: str, release_stream: str, release_name: str):
        api_path = f"/api/v1/releasestream/{quote(release_stream)}/release/{quote(release_name)}"
        full_url = f"{release_controller_url}{api_path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                release_info = await response.json()
                return release_info.get("phase")

    async def get_advisory_image_list(self, image_advisory: int):
        cmd = [
            "elliott",
            "advisory-images",
            "-a",
            f"{image_advisory}",
        ]
        async with self._elliott_lock:
            _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, stderr=None)
        return stdout

    async def send_image_list_email(self, release_name: str, advisory: int, archive_dir: Path):
        content = await self.get_advisory_image_list(advisory)
        subject = f"OCP {release_name} Image List"
        return await exectools.to_thread(self._mail.send_mail, self.runtime.config["email"][f"promote_image_list_recipients"], subject, content, archive_dir=archive_dir, dry_run=self.runtime.dry_run)


@cli.command("promote")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly. e.g. 4.9.1")
@click.option("--release-offset", "-r", metavar="OFFSET", type=int,
              help="Use this option if assembly type is custom. If offset is X for 4.9, release name will become 4.9.X-assembly.ASSEMBLY_NAME.")
@click.option("--arch", "arches", metavar="ARCH", multiple=True,
              help="[Multiple] Only promote given arch-specific release image. If not specified, this job will promote all architectures defined in group config.")
@click.option("--skip-blocker-bug-check", is_flag=True,
              help="Skip blocker bug check. Note block bugs are never checked for CUSTOM and CANDIDATE releases.")
@click.option("--skip-attached-bug-check", is_flag=True,
              help="Skip attached bug check. Note attached bugs are never checked for CUSTOM and CANDIDATE releases.")
@click.option("--skip-image-list", is_flag=True,
              help="Do not gather an advisory image list for docs.")
@click.option("--permit-overwrite", is_flag=True,
              help="DANGER! Allows the pipeline to overwrite an existing payload.")
@pass_runtime
@click_coroutine
async def promote(runtime: Runtime, group: str, assembly: str, release_offset: Optional[int],
                  arches: Tuple[str, ...], skip_blocker_bug_check: bool, skip_attached_bug_check: bool, skip_image_list: bool, permit_overwrite: bool):
    pipeline = PromotePipeline(runtime, group, assembly, release_offset, arches,
                               skip_blocker_bug_check, skip_attached_bug_check, skip_image_list,
                               permit_overwrite)
    await pipeline.run()
