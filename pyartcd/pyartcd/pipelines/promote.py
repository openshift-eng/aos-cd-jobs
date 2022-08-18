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
from doozerlib.util import (brew_arch_for_go_arch, brew_suffix_for_arch,
                            go_arch_for_brew_arch, go_suffix_for_arch)
from pyartcd import constants, exectools, util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.exceptions import VerificationError
from pyartcd.runtime import Runtime
from ruamel.yaml import YAML
from semver import VersionInfo
from tenacity import (RetryCallState, RetryError, retry,
                      retry_if_exception_type, retry_if_result,
                      stop_after_attempt, wait_fixed)

yaml = YAML(typ="safe")
yaml.default_flow_style = False


class PromotePipeline:
    DEST_RELEASE_IMAGE_REPO = constants.RELEASE_IMAGE_REPO

    def __init__(self, runtime: Runtime, group: str, assembly: str, release_offset: Optional[int],
                 arches: Iterable[str], skip_blocker_bug_check: bool = False,
                 skip_attached_bug_check: bool = False, skip_attach_cve_flaws: bool = False,
                 skip_image_list: bool = False, permit_overwrite: bool = False,
                 no_multi: bool = False, multi_only: bool = False, use_multi_hack: bool = False) -> None:
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.release_offset = release_offset
        self.arches = list(arches)
        if "multi" in self.arches:
            raise ValueError("`multi` is not a real architecture. Set multi_arch.enable to true to enable heterogenous payload support.")
        self.skip_blocker_bug_check = skip_blocker_bug_check
        self.skip_attached_bug_check = skip_attached_bug_check
        self.skip_attach_cve_flaws = skip_attach_cve_flaws
        self.skip_image_list = skip_image_list
        self.permit_overwrite = permit_overwrite

        if multi_only and no_multi:
            raise ValueError("Option multi_only can't be used with no_multi")
        self.no_multi = no_multi
        self.multi_only = multi_only
        self.use_multi_hack = use_multi_hack
        self._multi_enabled = False

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
        slack_response = await self._slack_client.say(f"Promoting release `{release_name}` @release-artists")
        slack_thread = slack_response["message"]["ts"]

        justifications = []
        try:
            self._multi_enabled = group_config.get("multi_arch", {}).get("enabled", False)
            if self.multi_only and not self._multi_enabled:
                raise ValueError("Can't promote a multi payload: multi_arch.enabled is not set in group config")
            # Get arches
            arches = self.arches or group_config.get("arches", [])
            arches = list(set(map(brew_arch_for_go_arch, arches)))
            if not arches:
                raise ValueError("No arches specified.")
            # Get previous list
            upgrades_str: Optional[str] = group_config.get("upgrades")
            if upgrades_str is None and assembly_type != assembly.AssemblyTypes.CUSTOM:
                raise ValueError(f"Group config for assembly {self.assembly} is missing the required `upgrades` field. If no upgrade edges are expected, please explicitly set the `upgrades` field to empty string.")
            previous_list = list(map(lambda s: s.strip(), upgrades_str.split(","))) if upgrades_str else []
            # Ensure all versions in previous list are valid semvers.
            if any(map(lambda version: not VersionInfo.isvalid(version), previous_list)):
                raise ValueError("Previous list (`upgrades` field in group config) has an invalid semver.")

            impetus_advisories = group_config.get("advisories", {})

            # Check for blocker bugs
            if self.skip_blocker_bug_check or assembly_type in [assembly.AssemblyTypes.CANDIDATE, assembly.AssemblyTypes.CUSTOM]:
                logger.info("Blocker Bug check is skipped.")
            else:
                logger.info("Checking for blocker bugs...")
                # TODO: Needs an option in releases.yml to skip this check
                try:
                    await self.check_blocker_bugs()
                except VerificationError as err:
                    logger.warn("Blocker bugs found for release: %s", err)
                    justification = self._reraise_if_not_permitted(err, "BLOCKER_BUGS", permits)
                    justifications.append(justification)
                logger.info("No blocker bugs found.")

            if not self.skip_attach_cve_flaws:
                # If there are CVEs, convert RHBAs to RHSAs and attach CVE flaw bugs
                tasks = []
                for impetus, advisory in impetus_advisories.items():
                    if not advisory:
                        continue
                    if advisory < 0 and assembly_type != assembly.AssemblyTypes.CANDIDATE:  # placeholder advisory id is still in group config?
                        raise ValueError("Found invalid %s advisory %s", impetus, advisory)
                    logger.info("Attaching CVE flaws for %s advisory %s...", impetus, advisory)
                    tasks.append(self.attach_cve_flaws(advisory))
                try:
                    await asyncio.gather(*tasks)
                except ChildProcessError as err:
                    logger.warn("Error attaching CVE flaw bugs: %s", err)
                    justification = self._reraise_if_not_permitted(err, "CVE_FLAWS", permits)
                    justifications.append(justification)
            else:
                self._logger.warning("Attaching CVE flaws is skipped.")

            # Attempt to move all advisories to QE

            tasks = []
            for impetus, advisory in impetus_advisories.items():
                if not advisory:
                    continue
                logger.info("Moving advisory %s to QE...", advisory)
                if not self.runtime.dry_run:
                    tasks.append(self.change_advisory_state(advisory, "QE"))
                else:
                    logger.warning("[DRY RUN] Would have moved advisory %s to QE", advisory)
            try:
                await asyncio.gather(*tasks)
            except ChildProcessError as err:
                logger.warn("Error moving advisory %s to QE: %s", advisory, err)

            # Ensure the image advisory is in QE (or later) state.
            image_advisory = impetus_advisories.get("image", 0)
            errata_url = ""

            if assembly_type == assembly.AssemblyTypes.STANDARD:
                if image_advisory <= 0:
                    err = VerificationError(f"No associated image advisory for {self.assembly} is defined.")
                    justification = self._reraise_if_not_permitted(err, "NO_ERRATA", permits)
                    justifications.append(justification)
                else:
                    logger.info("Verifying associated image advisory %s...", image_advisory)
                    image_advisory_info = await self.get_advisory_info(image_advisory)
                    try:
                        self.verify_image_advisory(image_advisory_info)
                        live_id = self.get_live_id(image_advisory_info)
                        assert live_id
                        errata_url = f"https://access.redhat.com/errata/{live_id}"  # don't quote
                    except VerificationError as err:
                        logger.warn("%s", err)
                        justification = self._reraise_if_not_permitted(err, "INVALID_ERRATA_STATUS", permits)
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
            metadata = {}
            description = group_config.get("description")
            if description:
                logger.warning("The following description message will be included in the metadata of release image: %s", description)
                metadata["description"] = str(description)
            if errata_url:
                metadata["url"] = errata_url
            reference_releases = util.get_assembly_basis(releases_config, self.assembly).get("reference_releases", {})
            tag_stable = assembly_type in [assembly.AssemblyTypes.STANDARD, assembly.AssemblyTypes.CANDIDATE]
            release_infos = await self.promote(release_name, arches, previous_list, metadata, reference_releases, tag_stable)
            self._logger.info("All release images for %s have been promoted.", release_name)

            # Wait for payloads to be accepted by release controllers
            pullspecs = {arch: release_info["image"] for arch, release_info in release_infos.items()}
            pullspecs_repr = ", ".join(f"{arch}: {pullspecs[arch]}" for arch in sorted(pullspecs.keys()))
            if not tag_stable:
                self._logger.warning("Release %s will not appear on release controllers. Pullspecs: %s", release_name, pullspecs_repr)
                await self._slack_client.say(f"Release {release_name} is ready. It will not appear on the release controllers. Please tell the user to manually pull the release images: {pullspecs_repr}", slack_thread)
            else:  # Wait for release images to be accepted by the release controllers
                self._logger.info("All release images for %s have been successfully promoted. Pullspecs: %s", release_name, pullspecs_repr)

                # check if release is already accepted (in case we timeout and run the job again)
                tasks = []
                for arch, release_info in release_infos.items():
                    go_arch_suffix = go_suffix_for_arch(arch)
                    release_stream = f"4-stable{go_arch_suffix}"
                    actual_release_name = release_info["metadata"]["version"]
                    # Currently the multi payload uses a different release name to workaround a cincinnati issue.
                    # Use the release name in release_info instead.
                    tasks.append(self.is_accepted(actual_release_name, arch, release_stream))
                accepted = await asyncio.gather(*tasks)

                if not all(accepted):
                    self._logger.info("Determining upgrade tests...")
                    test_commands = self._get_upgrade_tests_commands(release_name, previous_list)
                    message = f"""A new release `{release_name}` is ready and needs some upgrade tests to be triggered.
Please open a chat with @cluster_bot and issue each of these lines individually:
{os.linesep.join(test_commands)}
        """
                    await self._slack_client.say(message, slack_thread)

                    self._logger.info("Waiting for release images for %s to be accepted by the release controller...", release_name)
                    tasks = []
                    for arch, release_info in release_infos.items():
                        go_arch_suffix = go_suffix_for_arch(arch)
                        release_stream = f"4-stable{go_arch_suffix}"
                        actual_release_name = release_info["metadata"]["version"]
                        # Currently the multi payload uses a different release name to workaround a cincinnati issue.
                        # Use the release name in release_info instead.
                        tasks.append(self.wait_for_stable(actual_release_name, arch, release_stream))
                    try:
                        await asyncio.gather(*tasks)
                    except RetryError as err:
                        message = f"Timeout waiting for release to be accepted by the release controllers: {err}"
                        self._logger.error(message)
                        self._logger.exception(err)
                        raise TimeoutError(message)

                self._logger.info("All release images for %s have been accepted by the release controllers.", release_name)

                message = f"Release `{release_name}` has been accepted by the release controllers."
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
            message = f"Promoting release {release_name} failed with: {error_message}"
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
        if image_advisory > 0:
            data["advisory"] = image_advisory
        if errata_url:
            data["live_url"] = errata_url
        for arch, release_info in release_infos.items():
            data["content"][arch] = {
                "pullspec": release_info["image"],
                "digest": release_info["digest"],
                "metadata": {k: release_info["metadata"][k] for k in release_info["metadata"].keys() & {'version', 'previous'}},
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
        self._logger.warn("Issue %s is permitted with justification: %s", err, justification)
        return justification

    async def change_advisory_state(self, advisory: int, state: str):
        cmd = [
            "elliott",
            "change-state",
            "-s",
            state,
            "-a",
            str(advisory),
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")
        async with self._elliott_lock:
            await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, stdout=sys.stderr)

    async def check_blocker_bugs(self):
        # Note: --assembly option should always be "stream". We are checking blocker bugs for this release branch regardless of the sweep cutoff timestamp.
        cmd = [
            "elliott",
            f"--group={self.group}",
            "--assembly=stream",
            "find-bugs:blocker",
        ]
        async with self._elliott_lock:
            _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, stderr=None)
        match = re.search(r"Found ([0-9]+) bugs", stdout)
        if not match:
            raise IOError(f"Could determine whether this release has blocker bugs. Elliott printed unexpected message: {stdout}")
        if int(match[1]) != 0:
            raise VerificationError(f"{int(match[1])} blocker Bug(s) found for release; do not proceed without resolving. See https://art-docs.engineering.redhat.com/release/4.y.z-stream/#handling-blocker-bugs. To permit this validation error, see https://art-docs.engineering.redhat.com/jenkins/build-promote-assembly-readme/#permit-certain-validation-failures. Elliott output: {stdout}")

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
            f"--assembly={self.assembly}",
            f"--group={self.group}",
            "verify-attached-bugs",
            "--verify-flaws"
        ]
        async with self._elliott_lock:
            await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, stdout=sys.stderr)

    async def promote(self, release_name: str, arches: List[str], previous_list: List[str], metadata: Optional[Dict], reference_releases: Dict[str, str], tag_stable: bool):
        """ Promote all release payloads
        :param release_name: Release name. e.g. 4.11.0-rc.6
        :param arches: List of architecture names. e.g. ["x86_64", "s390x"]. Don't use "multi" in this parameter.
        :param previous_list: Previous list.
        :param metadata: Payload metadata
        :param reference_releases: A dict of reference release payloads to promote. Keys are architecture names, values are payload pullspecs
        :param tag_stable: Whether to tag the promoted payload to "4-stable[-$arch]" release stream.
        :return: A dict. Keys are architecture name or "multi", values are release_info dicts.
        """
        tasks = OrderedDict()
        if not self.no_multi and self._multi_enabled:
            tasks["heterogeneous"] = self._promote_heterogeneous_payload(release_name, arches, previous_list, metadata, tag_stable)
        else:
            self._logger.warning("Multi/heterogeneous payload is disabled.")
        if not self.multi_only:
            tasks["homogeneous"] = self._promote_homogeneous_payloads(release_name, arches, previous_list, metadata, reference_releases, tag_stable)
        else:
            self._logger.warning("Arch-specific homogeneous release payloads will not be promoted because --multi-only is set.")
        try:
            results = dict(zip(tasks.keys(), await asyncio.gather(*tasks.values())))
        except ChildProcessError as err:
            self._logger.error("Error promoting release images: %s\n%s", str(err), traceback.format_exc())
            raise
        return_value = {}
        if "homogeneous" in results:
            return_value.update(results["homogeneous"])
        if "heterogeneous" in results:
            return_value["multi"] = results["heterogeneous"]
        return return_value

    async def _promote_homogeneous_payloads(self, release_name: str, arches: List[str], previous_list: List[str], metadata: Optional[Dict], reference_releases: Dict[str, str], tag_stable: bool):
        """ Promote homogeneous payloads for specified architectures
        :param release_name: Release name. e.g. 4.11.0-rc.6
        :param arches: List of architecture names. e.g. ["x86_64", "s390x"].
        :param previous_list: Previous list.
        :param metadata: Payload metadata
        :param reference_releases: A dict of reference release payloads to promote. Keys are architecture names, values are payload pullspecs
        :param tag_stable: Whether to tag the promoted payload to "4-stable[-$arch]" release stream.
        :return: A dict. Keys are architecture name, values are release_info dicts.
        """
        tasks = []
        for arch in arches:
            tasks.append(self._promote_arch(release_name, arch, previous_list, metadata, reference_releases.get(arch), tag_stable))
        release_infos = await asyncio.gather(*tasks)
        return dict(zip(arches, release_infos))

    async def _promote_arch(self, release_name: str, arch: str, previous_list: List[str], metadata: Optional[Dict], reference_release: Optional[str], tag_stable: bool):
        """ Promote an arch-specific homogeneous payload
        :param arch: Architecture name.
        :param previous_list: Previous list.
        :param metadata: Payload metadata
        :param reference_releases: A dict of reference release payloads to promote. Keys are architecture names, values are payload pullspecs
        :param tag_stable: Whether to tag the promoted payload to "4-stable[-$arch]" release stream.
        :return: A dict. Keys are architecture name, values are release_info dicts.
        """
        go_arch_suffix = go_suffix_for_arch(arch, is_private=False)
        brew_arch = brew_arch_for_go_arch(arch)  # ensure we are using Brew arches (e.g. aarch64) instead of golang arches (e.g. arm64).
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
            major, minor = util.isolate_major_minor_in_group(self.group)
            # The imagestream for the assembly in ocp-multi contains a single tag.
            # That single istag points to a top-level manifest-list on quay.io.
            # Each entry in the manifest-list is an arch-specific heterogeneous payload.
            # We need to fetch that manifest-list and recreate all arch-specific heterogeneous payloads first,
            # then recreate the top-level manifest-list.
            is_name = f"{major}.{minor}-art-assembly-{self.assembly}{go_arch_suffix}"
            multi_is = await self.get_image_stream("ocp{go_arch_suffix}", is_name)
            if not multi_is:
                raise ValueError(f"Image stream {is_name} is not found. Did you run build-sync?")
            self._logger.info("Building arch-specific release image %s for %s (%s)...", release_name, arch, dest_image_pullspec)
            reference_pullspec = None
            source_image_stream = None
            if reference_release:
                reference_pullspec = f"registry.ci.openshift.org/ocp{go_arch_suffix}/release{go_arch_suffix}:{reference_release}"
            else:
                major, minor = util.isolate_major_minor_in_group(self.group)
                source_image_stream = f"{major}.{minor}-art-assembly-{self.assembly}{go_arch_suffix}"
            await self.build_release_image(release_name, brew_arch, previous_list, metadata, dest_image_pullspec, reference_pullspec, source_image_stream, keep_manifest_list=False)
            self._logger.info("Release image for %s %s has been built and pushed to %s", release_name, arch, dest_image_pullspec)
            self._logger.info("Getting release image information for %s...", dest_image_pullspec)
            if not self.runtime.dry_run:
                dest_image_info = await self.get_release_image_info(dest_image_pullspec, raise_if_not_found=True)
            else:
                # populate fake data for dry run
                dest_image_info = {
                    "image": f"example.com/fake-release:{release_name}{brew_suffix_for_arch(arch)}",
                    "digest": f"fake:deadbeef{brew_suffix_for_arch(arch)}",
                    "metadata": {
                        "version": release_name,
                        "previous": previous_list,
                    },
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
                    go_arch_suffix = go_suffix_for_arch(arch, is_private=False)
                    dest_image_info["references"]["metadata"] = {"annotations": {"release.openshift.io/from-image-stream": f"fake{go_arch_suffix}/{major}.{minor}-art-assembly-{self.assembly}{go_arch_suffix}"}}

        if not tag_stable:
            self._logger.info("Release image %s will not appear on the release controller.", dest_image_pullspec)
            return dest_image_info

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

    async def _promote_heterogeneous_payload(self, release_name: str, include_arches: List[str], previous_list: List[str], metadata: Optional[Dict], tag_stable: bool):
        """ Promote heterogeneous payload.
        The heterogeneous payload itself is a manifest list, which include references to arch-specific heterogeneous payloads.
        :param release_name: Release name. e.g. 4.11.0-rc.6
        :param include_arches: List of architecture names.
        :param previous_list: Previous list.
        :param metadata: Payload metadata
        :param tag_stable: Whether to tag the promoted payload to "4-stable[-$arch]" release stream.
        :return: A dict. Keys are architecture name, values are release_info dicts.
        """
        dest_image_tag = f"{release_name}-multi"
        dest_image_pullspec = f"{self.DEST_RELEASE_IMAGE_REPO}:{dest_image_tag}"
        self._logger.info("Checking if multi/heterogeneous payload %s exists...", dest_image_pullspec)
        dest_image_digest = await self.get_image_digest(dest_image_pullspec)
        if dest_image_digest:  # already promoted
            self._logger.warning("Multi/heterogeneous payload %s already exists; digest: %s", dest_image_pullspec, dest_image_digest)
            dest_manifest_list = await self.get_image_info(dest_image_pullspec, raise_if_not_found=True)

        if self.use_multi_hack:
            # Add '-multi' to heterogeneous payload name.
            # This is to workaround a cincinnati issue discussed in #incident-cincinnati-sha-mismatch-for-multi-images
            # and prevent the heterogeneous payload from getting into Cincinnati channels.
            # e.g.
            #   "4.11.0-rc.6" => "4.11.0-multi-rc.6"
            #   "4.11.0" => "4.11.0-multi"
            parsed_version = VersionInfo.parse(release_name)
            parsed_version = parsed_version.replace(prerelease=f"multi-{parsed_version.prerelease}" if parsed_version.prerelease else "multi")
            release_name = str(parsed_version)
            # No previous list is required until we get rid of the "having `-multi` string in the release name" workaround
            previous_list = []

        if not dest_image_digest or self.permit_overwrite:
            if dest_image_digest:
                self._logger.warning("The existing payload %s will be overwritten!", dest_image_pullspec)
            major, minor = util.isolate_major_minor_in_group(self.group)
            # The imagestream for the assembly in ocp-multi contains a single tag.
            # That single istag points to a top-level manifest-list on quay.io.
            # Each entry in the manifest-list is an arch-specific heterogeneous payload.
            # We need to fetch that manifest-list and recreate all arch-specific heterogeneous payloads first,
            # then recreate the top-level manifest-list.
            multi_is_name = f"{major}.{minor}-art-assembly-{self.assembly}-multi"
            multi_is = await self.get_image_stream("ocp-multi", multi_is_name)
            if not multi_is:
                raise ValueError(f"Image stream {multi_is_name} is not found. Did you run build-sync?")
            if len(multi_is["spec"]["tags"]) != 1:
                raise ValueError(f"Image stream {multi_is_name} should only contain a single tag; Found {len(multi_is['spec']['tags'])} tags")
            multi_ist = multi_is["spec"]["tags"][0]
            source_manifest_list = await self.get_image_info(multi_ist["from"]["name"], raise_if_not_found=True)
            if source_manifest_list["mediaType"] != "application/vnd.docker.distribution.manifest.list.v2+json":
                raise ValueError(f'Pullspec {multi_ist["from"]["name"]} doesn\'t point to a valid manifest list.')
            source_repo = multi_ist["from"]["name"].rsplit(':', 1)[0].rsplit('@', 1)[0]  # quay.io/openshift-release-dev/ocp-release@sha256:deadbeef -> quay.io/openshift-release-dev/ocp-release
            # dest_manifest_list is the final top-level manifest-list
            dest_manifest_list = {
                "image": dest_image_pullspec,
                "manifests": []
            }
            build_tasks = []
            for manifest in source_manifest_list["manifests"]:
                os = manifest["platform"]["os"]
                arch = manifest["platform"]["architecture"]
                brew_arch = brew_arch_for_go_arch(arch)
                if os != "linux" or brew_arch not in include_arches:
                    self._logger.warning(f"Skipping {os}/{arch} in manifest_list {source_manifest_list}")
                    continue
                arch_payload_source = f"{source_repo}@{manifest['digest']}"
                arch_payload_dest = f"{dest_image_pullspec}-{brew_arch}"
                # Add an entry to the top-level manifest list
                dest_manifest_list["manifests"].append({
                    'image': arch_payload_dest,
                    'platform': {
                        'os': 'linux',
                        'architecture': arch
                    }
                })
                # Add task to build arch-specific heterogeneous payload
                metadata = metadata.copy() if metadata else {}
                metadata['release.openshift.io/architecture'] = 'multi'
                build_tasks.append(self.build_release_image(release_name, brew_arch, previous_list, metadata, arch_payload_dest, arch_payload_source, None, keep_manifest_list=True))

            # Build and push all arch-specific heterogeneous payloads
            self._logger.info("Building arch-specific heterogeneous payloads for %s...", include_arches)
            await asyncio.gather(*build_tasks)

            # Push the top level manifest list
            self._logger.info("Pushing manifest list...")
            await self.push_manifest_list(release_name, dest_manifest_list)
            self._logger.info("Heterogeneous release payload for %s has been built. Manifest list pullspec is %s", release_name, dest_image_pullspec)
            self._logger.info("Getting release image information for %s...", dest_image_pullspec)
            dest_image_digest = await self.get_image_digest(dest_image_pullspec, raise_if_not_found=True) if not self.runtime.dry_run else "fake:deadbeef-multi"

        dest_image_info = dest_manifest_list.copy()
        dest_image_info["image"] = dest_image_pullspec
        dest_image_info["digest"] = dest_image_digest
        dest_image_info["metadata"] = {
            "version": release_name,
        }
        if not tag_stable:
            self._logger.info("Release image %s will not appear on the release controller.", dest_image_pullspec)
            return dest_image_info

        # Check if the heterogeneous release payload is already tagged into the image stream.
        namespace = f"ocp-multi"
        image_stream_tag = f"release-multi:{release_name}"
        namespace_image_stream_tag = f"{namespace}/{image_stream_tag}"
        self._logger.info("Checking if ImageStreamTag %s exists...", namespace_image_stream_tag)
        ist = await self.get_image_stream_tag(namespace, image_stream_tag)
        if ist:
            ist_pullspec = ist["tag"]["from"]["name"]
            if ist_pullspec == dest_image_pullspec:
                self._logger.info("ImageStreamTag %s already exists and points to %s.", namespace_image_stream_tag, dest_image_pullspec)
                return dest_image_info
            message = f"ImageStreamTag {namespace_image_stream_tag} already exists, but it points to {ist_pullspec} instead of {dest_image_pullspec}"
            if not self.permit_overwrite:
                raise ValueError(message)
            self._logger.warning(message)
        else:
            self._logger.info("ImageStreamTag %s doesn't exist.", namespace_image_stream_tag)

        self._logger.info("Tagging release image %s into %s...", dest_image_pullspec, namespace_image_stream_tag)
        await self.tag_release(dest_image_pullspec, namespace_image_stream_tag)
        self._logger.info("Release image %s has been tagged into %s.", dest_image_pullspec, namespace_image_stream_tag)
        return dest_image_info

    async def push_manifest_list(self, release_name: str, dest_manifest_list: Dict):
        dest_manifest_list_path = self._working_dir / f"{release_name}.manifest-list.yaml"
        with dest_manifest_list_path.open("w") as ml:
            yaml.dump(dest_manifest_list, ml)
        cmd = [
            "manifest-tool", "push", "from-spec", "--", f"{dest_manifest_list_path}"
        ]
        if self.runtime.dry_run:
            self._logger.warning("[DRY RUN] Would have run %s", cmd)
            return
        env = os.environ.copy()
        await exectools.cmd_assert_async(cmd, env=env, stdout=sys.stderr)

    @staticmethod
    async def get_release_image_info(pullspec: str, raise_if_not_found: bool = False):
        cmd = ["oc", "adm", "release", "info", "-o", "json", "--", pullspec]
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        rc, stdout, stderr = await exectools.cmd_gather_async(cmd, check=False, env=env)
        if rc != 0:
            if "not found: manifest unknown" in stderr or "was deleted or has expired" in stderr:
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

    async def build_release_image(self, release_name: str, arch: str, previous_list: List[str], metadata: Optional[Dict],
                                  dest_image_pullspec: str, source_image_pullspec: Optional[str], source_image_stream: Optional[str], keep_manifest_list: bool):
        if bool(source_image_pullspec) + bool(source_image_stream) != 1:
            raise ValueError("Specify one of source_image_pullspec or source_image_stream")
        go_arch_suffix = go_suffix_for_arch(arch, is_private=False)
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
        if source_image_pullspec:
            cmd.append(f"--from-release={source_image_pullspec}")
        if source_image_stream:
            cmd.extend(["--reference-mode=source", f"--from-image-stream={source_image_stream}"])
        if keep_manifest_list:
            cmd.append("--keep-manifest-list")

        if previous_list:
            cmd.append(f"--previous={','.join(previous_list)}")
        if metadata:
            cmd.append("--metadata")
            cmd.append(json.dumps(metadata))
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        self._logger.info("Running %s", " ".join(cmd))
        await exectools.cmd_assert_async(cmd, env=env, stdout=sys.stderr)
        pass

    @staticmethod
    async def get_image_stream(namespace: str, image_stream: str):
        cmd = [
            "oc",
            "-n",
            namespace,
            "get",
            "imagestream",
            "-o",
            "json",
            "--ignore-not-found",
            "--",
            image_stream,
        ]
        env = os.environ.copy()
        env["GOTRACEBACK"] = "all"
        _, stdout, _ = await exectools.cmd_gather_async(cmd, env=env, stderr=None)
        stdout = stdout.strip()
        if not stdout:  # Not found
            return None
        return json.loads(stdout)

    @staticmethod
    async def get_image_info(pullspec: str, raise_if_not_found: bool = False):
        # Get image manifest/manifest-list.
        # We use skopeo instead of `oc image info` because oc doesn't support json/yaml output for a manifest list.
        if "://" not in pullspec:
            pullspec = f"docker://{pullspec}"
        # skopeo on buildvm is too old. Use a containerized version instead.
        cmd = [
            "podman",
            "run",
            "--rm",
            "--privileged",
            "quay.io/containers/skopeo:v1.8"
        ]
        if os.environ.get("PYARTCD_USE_NATIVE_SKOPEO") == "1":
            cmd = ["skopeo"]
        cmd.extend([
            "inspect",
            "--no-tags",
            "--raw",
            "--",
            pullspec,
        ])
        env = os.environ.copy()
        rc, stdout, stderr = await exectools.cmd_gather_async(cmd, check=False, env=env)
        if rc != 0:
            if "not found: manifest unknown" in stderr or "was deleted or has expired" in stderr:
                # image doesn't exist
                if raise_if_not_found:
                    raise IOError(f"Image {pullspec} is not found.")
                return None
            raise ChildProcessError(f"Error running {cmd}: exit_code={rc}, stdout={stdout}, stderr={stderr}")
        info = json.loads(stdout)
        if not isinstance(info, dict):
            raise ValueError(f"Invalid image info: {info}")
        return info

    @staticmethod
    async def get_image_digest(pullspec: str, raise_if_not_found: bool = False):
        # Get image digest
        # We use skopeo instead of `oc image info` because oc doesn't support json/yaml output for a manifest list.
        if "://" not in pullspec:
            pullspec = f"docker://{pullspec}"
        # skopeo on buildvm is too old. Use a containerized version instead.
        cmd = [
            "podman",
            "run",
            "--rm",
            "--privileged",
            "quay.io/containers/skopeo:v1.8"
        ]
        if os.environ.get("PYARTCD_USE_NATIVE_SKOPEO") == "1":
            cmd = ["skopeo"]
        cmd.extend([
            "inspect",
            "--no-tags",
            "--format={{.Digest}}",
            "--",
            pullspec,
        ])
        env = os.environ.copy()
        rc, stdout, stderr = await exectools.cmd_gather_async(cmd, check=False, env=env)
        if rc != 0:
            if "manifest unknown" in stderr or "was deleted or has expired" in stderr:
                # image doesn't exist
                if raise_if_not_found:
                    raise IOError(f"Image {pullspec} is not found.")
                return None
            raise ChildProcessError(f"Error running {cmd}: exit_code={rc}, stdout={stdout}, stderr={stderr}")
        return stdout.strip()

    @staticmethod
    async def get_image_stream_tag(namespace: str, image_stream_tag: str):
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

    async def is_accepted(self, release_name: str, arch: str, release_stream: str):
        go_arch = go_arch_for_brew_arch(arch)
        release_controller_url = f"https://{go_arch}.ocp.releases.ci.openshift.org"
        phase = await self.get_release_phase(release_controller_url, release_stream, release_name)
        return phase == "Accepted"

    async def wait_for_stable(self, release_name: str, arch: str, release_stream: str):
        go_arch = go_arch_for_brew_arch(arch)
        release_controller_url = f"https://{go_arch}.ocp.releases.ci.openshift.org"
        if self.runtime.dry_run:
            actual_phase = await self.get_release_phase(release_controller_url, release_stream, release_name)
            self._logger.warning("[DRY RUN] Release %s for %s has phase %s. Assume accepted.", release_name, arch, actual_phase)
            return

        def _my_before_sleep(retry_state: RetryCallState):
            if retry_state.outcome.failed:
                err = retry_state.outcome.exception()
                self._logger.warning(
                    'Error communicating with %s release controller. Will check again in %s seconds. %s: %s',
                    arch, retry_state.next_action.sleep, type(err).__name__, err,
                )
            else:
                self._logger.log(
                    logging.INFO if retry_state.attempt_number < 1 else logging.WARNING,
                    'Release payload for "%s" arch is in the "%s" phase. Will check again in %s seconds.',
                    arch, retry_state.outcome.result(), retry_state.next_action.sleep
                )
        return await retry(
            stop=(stop_after_attempt(72)),  # wait for 10m * 72 = 720m = 12 hours
            wait=wait_fixed(600),  # wait for 10 minutes between retries
            retry=(retry_if_result(lambda phase: phase != "Accepted") | retry_if_exception_type()),
            before_sleep=_my_before_sleep,
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
        return await exectools.to_thread(self._mail.send_mail, self.runtime.config["email"]["promote_image_list_recipients"], subject, content, archive_dir=archive_dir, dry_run=self.runtime.dry_run)


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
@click.option("--skip-attach-cve-flaws", is_flag=True,
              help="Skip attaching CVE flaws.")
@click.option("--skip-image-list", is_flag=True,
              help="Do not gather an advisory image list for docs.")
@click.option("--permit-overwrite", is_flag=True,
              help="DANGER! Allows the pipeline to overwrite an existing payload.")
@click.option("--no-multi", is_flag=True, help="Do not promote a multi-arch/heterogeneous payload.")
@click.option("--multi-only", is_flag=True, help="Do not promote arch-specific homogenous payloads.")
@click.option("--use-multi-hack", is_flag=True, help="Add '-multi' to heterogeneous payload name to workaround a Cincinnati issue")
@pass_runtime
@click_coroutine
async def promote(runtime: Runtime, group: str, assembly: str, release_offset: Optional[int],
                  arches: Tuple[str, ...], skip_blocker_bug_check: bool, skip_attached_bug_check: bool,
                  skip_attach_cve_flaws: bool, skip_image_list: bool,
                  permit_overwrite: bool, no_multi: bool, multi_only: bool, use_multi_hack: bool):
    pipeline = PromotePipeline(runtime, group, assembly, release_offset, arches,
                               skip_blocker_bug_check, skip_attached_bug_check, skip_attach_cve_flaws,
                               skip_image_list, permit_overwrite, no_multi, multi_only, use_multi_hack)
    await pipeline.run()
