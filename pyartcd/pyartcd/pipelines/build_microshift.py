import asyncio
import json
import logging
import os
import re
import traceback
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, Optional, Tuple, cast

import click
from doozerlib.assembly import AssemblyTypes
from doozerlib.util import (brew_arch_for_go_arch,
                            isolate_nightly_name_components)
import ruamel.yaml
import sys
import io
from semver import VersionInfo

from pyartcd import constants, exectools, oc, util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.git import GitRepository
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from pyartcd.util import (get_assembly_basis, get_assembly_type,
                          isolate_el_version_in_release, load_group_config,
                          load_releases_config)


class BuildMicroShiftPipeline:
    """ Rebase and build MicroShift for an assembly """

    SUPPORTED_ASSEMBLY_TYPES = {AssemblyTypes.STANDARD, AssemblyTypes.CANDIDATE, AssemblyTypes.PREVIEW, AssemblyTypes.STREAM, AssemblyTypes.CUSTOM}

    def __init__(self, runtime: Runtime, group: str, assembly: str, payloads: Tuple[str, ...], no_rebase: bool,
                 force: bool, ocp_build_data_url: str, logger: Optional[logging.Logger] = None):
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.payloads = payloads
        self.no_rebase = no_rebase
        self.force = force
        self._logger = logger or runtime.logger
        self._working_dir = self.runtime.working_dir.absolute()

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
        if not match:
            raise ValueError(f"Invalid group name: {group}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Elliott and Doozer
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self._working_dir / "elliott-working")
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._working_dir / "doozer-working")

        if not ocp_build_data_url:
            ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        if ocp_build_data_url:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = ocp_build_data_url
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = ocp_build_data_url

    async def run(self):
        slack_client = None
        try:
            group_config = await load_group_config(self.group, self.assembly, env=self._doozer_env_vars)
            releases_config = await load_releases_config(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"], "ocp-build-data"))
            assembly_type = get_assembly_type(releases_config, self.assembly)
            if assembly_type not in self.SUPPORTED_ASSEMBLY_TYPES:
                raise ValueError(f"Building MicroShift for assembly type {assembly_type.value} is not currently supported.")

            custom_payloads = None
            if assembly_type is AssemblyTypes.STREAM:
                # rebase against nightlies
                # rpm version-release will be like `4.12.0~test-202201010000.p?`
                if self.no_rebase:
                    # Without knowning the nightly name, it is hard to determine rpm version-release.
                    raise ValueError("--no-rebase is not supported to build against assembly stream.")
                if not self.payloads:
                    raise ValueError("Release payloads must be specified to rebase against assembly stream.")
                payload_infos = await self.parse_release_payloads(self.payloads)
                if "x86_64" not in payload_infos:
                    raise ValueError("x86_64 payload is required for rebasing microshift.")
                major, minor = util.isolate_major_minor_in_group(self.group)
                for info in payload_infos.values():
                    payload_version = VersionInfo.parse(info["version"])
                    if (payload_version.major, payload_version.minor) != (major, minor):
                        raise ValueError(f"Specified payload {info['pullspec']} does not match group major.minor {major}.{minor}: {payload_version}")
                release_name = payload_infos["x86_64"]["version"]  # use the version of the x86_64 payload to generate the rpm version-release.
                custom_payloads = payload_infos
            else:
                # rebase against named releases
                if self.payloads:
                    raise ValueError(f"Specifying payloads for assembly type {assembly_type.value} is not allowed.")
                release_name = util.get_release_name_for_assembly(self.group, releases_config, self.assembly)

            # For named releases, check if the build already exists
            nvrs = []
            pr = None

            if assembly_type is not AssemblyTypes.STREAM and not self.force:
                nvrs = await self._find_builds()

            if nvrs:
                self._logger.info("Builds already exist: %s", nvrs)
            else:
                # Rebases and builds microshift
                if assembly_type is not AssemblyTypes.STREAM:
                    slack_client = self.runtime.new_slack_client()
                    slack_client.bind_channel(self.group)
                    slack_response = await slack_client.say(f":construction: Build microshift for assembly {self.assembly} :construction:")
                    slack_thread = slack_response["message"]["ts"]
                version, release = self.generate_microshift_version_release(release_name)
                nvrs = await self._rebase_and_build_rpm(version, release, custom_payloads)

                # Create a PR to pin microshift build
                assembly_basis = get_assembly_basis(releases_config, self.assembly)
                if assembly_basis.brew_event:
                    pr = await self._update_release_in_pr(nvrs)

                # Sends a slack message
                if slack_client:
                    message = f"Assembly definition has been updated with {pr}"
                    if assembly_type is AssemblyTypes.PREVIEW:
                        message += "\n This is an EC release. Please run <https://saml.buildvm.hosts.prod.psi.bos.redhat.com:8888/job/aos-cd-builds/job/build%252Fmicroshift_sync/|microshift_sync> with `UPDATE_PUB_MIRROR` checked."
                    await slack_client.say(message, slack_thread)

            self._attach_builds(group_config.get("advisories").get("microshift"))

        except Exception as err:
            error_message = f"Error building microshift: {err}\n {traceback.format_exc()}"
            self._logger.error(error_message)
            if slack_client:
                await slack_client.say(error_message, slack_thread)
            raise

    @staticmethod
    async def parse_release_payloads(payloads: Iterable[str]):
        result = {}
        pullspecs = []
        for payload in payloads:
            if "/" not in payload:
                # Convert nightly name to pullspec
                # 4.12.0-0.nightly-2022-10-25-210451 ==> registry.ci.openshift.org/ocp/release:4.12.0-0.nightly-2022-10-25-210451
                _, brew_cpu_arch, _ = isolate_nightly_name_components(payload)
                pullspecs.append(constants.NIGHTLY_PAYLOAD_REPOS[brew_cpu_arch] + ":" + payload)
            else:
                # payload is a pullspec
                pullspecs.append(payload)
        payload_infos = await asyncio.gather(*(oc.get_release_image_info(pullspec) for pullspec in pullspecs))
        for info in payload_infos:
            arch = info["config"]["architecture"]
            brew_arch = brew_arch_for_go_arch(arch)
            version = info["metadata"]["version"]
            result[brew_arch] = {
                "version": version,
                "arch": arch,
                "pullspec": info["image"],
                "digest": info["digest"],
            }
        return result

    @staticmethod
    def generate_microshift_version_release(ocp_version: str, timestamp: Optional[str] = None):
        """ Generate version and release strings for microshift rpm.
        Example version-releases:
        - 4.12.42-202210011234
        - 4.13.0~rc.4-202210011234
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M") if not timestamp else timestamp
        release = f"{timestamp}.p?"
        release_version = VersionInfo.parse(ocp_version)
        version = f"{release_version.major}.{release_version.minor}.{release_version.patch}"
        if release_version.prerelease:
            version += f"~{release_version.prerelease.replace('-', '_')}"
        return version, release

    async def _find_builds(self) -> List[str]:
        """ Find microshift builds in Brew
        :param release: release field for rebase
        :return: NVRs
        """
        cmd = [
            "elliott",
            "--group", self.group,
            "--assembly", self.assembly,
            "-r", "microshift",
            "find-builds",
            "-k", "rpm",
            "--member-only",
        ]
        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/out.json"
            cmd.append(f"--json={path}")
            await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars)
            with open(path) as f:
                result = json.load(f)
        return cast(List[str], result["builds"])

    async def _attach_builds(self, advisory) -> List[str]:
        cmd = [
            "elliott",
            "--group", self.group,
            "--assembly", self.assembly,
            "-r", "microshift",
            "find-builds",
            "-k", "rpm",
            "--member-only",
            "--use-default-advisory", "microshift",
        ]
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars)
        cmd = [
            "elliott",
            "--group", self.group,
            "--assembly", self.assembly,
            "change-state",
            "-s", "QE",
            "-a", str(advisory),
        ]
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars)

    async def _rebase_and_build_rpm(self, version, release: str, custom_payloads: Optional[Dict[str, str]]) -> List[str]:
        """ Rebase and build RPM
        :param release: release field for rebase
        :return: NVRs
        """
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "-r", "microshift",
            "rpms:rebase-and-build",
            "--version", version,
            "--release", release,
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")
        set_env = self._doozer_env_vars.copy()
        if custom_payloads:
            set_env["MICROSHIFT_PAYLOAD_X86_64"] = custom_payloads["x86_64"]["pullspec"]
            set_env["MICROSHIFT_PAYLOAD_AARCH64"] = custom_payloads["aarch64"]["pullspec"]
        if self.no_rebase:
            set_env["MICROSHIFT_NO_REBASE"] = "1"
        await exectools.cmd_assert_async(cmd, env=set_env)

        if self.runtime.dry_run:
            return [f"microshift-{version}-{release.replace('.p?', '.p0')}.el8"]

        # parse record.log
        with open(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / "record.log", "r") as file:
            record_log = parse_record_log(file)
            return record_log["build_rpm"][-1]["nvrs"].split(",")

    def _pin_nvrs(self, nvrs: List[str], releases_config) -> Dict:
        """ Update releases.yml to pin the specified NVRs.
        Example:
            releases:
                4.11.7:
                    assembly:
                    members:
                        rpms:
                        - distgit_key: microshift
                        metadata:
                            is:
                                el8: microshift-4.11.7-202209300751.p0.g7ebffc3.assembly.4.11.7.el8
        """
        is_entry = {}
        dg_key = "microshift"
        for nvr in nvrs:
            el_version = isolate_el_version_in_release(nvr)
            assert el_version is not None
            is_entry[f"el{el_version}"] = nvr

        rpms_entry = releases_config["releases"][self.assembly].setdefault("assembly", {}).setdefault("members", {}).setdefault("rpms", [])
        microshift_entry = next(filter(lambda rpm: rpm.get("distgit_key") == dg_key, rpms_entry), None)
        if microshift_entry is None:
            microshift_entry = {"distgit_key": dg_key, "why": "Pin microshift to assembly"}
            rpms_entry.append(microshift_entry)
        microshift_entry.setdefault("metadata", {})["is"] = is_entry
        return microshift_entry

    async def _update_release_in_pr(self, nvrs: List[str]):
        branch = f"auto-pin-microshift-{self.group}-{self.assembly}"
        title = f"Pin microshift build for {self.group} {self.assembly}"
        body = f"Created by job run {self.runtime.get_job_run_url()}"
        repo=self.runtime.new_github_client().get_repo("openshift/ocp-build-data")
        microref=repo.create_git_ref(f"refs/heads/{branch}}",repo.get_git_ref(f"heads/{self.group}").object.sha) # create a microshift branch
        releasefile=repo.get_contents("releases.yml", ref=branch)
        yaml=ruamel.yaml.YAML()
        yaml.preserve_quotes = True
        releases_yaml = yaml.load(releasefile.decoded_content)
        self._pin_nvrs(nvrs, releases_yaml) # insert nvrs into release.yaml
        f=io.StringIO()
        yaml.dump(releases_yaml,f)
        f.seek(0)
        commit=repo.update_file(releasefile.path, "update microshift", f.read(), releasefile.sha, branch=branch) # update releases.yaml in microshift branch
        pr=repo.create_pull(title=title,body=body,head=f"openshift:{branch}", base={self.group}) # create pr from microshift to {group} branch
        pr.merge(merge_method="squash") # merge pr
        microref.delete() # delete microshift branch
        self._logger.info("Insert microshift nvr into releases.yaml complete")
        return pr.html_url


@cli.command("build-microshift")
@click.option("--ocp-build-data-url", metavar='BUILD_DATA', default=None,
              help=f"Git repo or directory containing groups metadata e.g. {constants.OCP_BUILD_DATA_URL}")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly to rebase & build for. e.g. 4.9.1")
@click.option("--payload", "payloads", metavar="PULLSPEC", multiple=True,
              help="[Multiple] Release payload to rebase against; Can be a nightly name or full pullspec")
@click.option("--no-rebase", is_flag=True,
              help="Don't rebase microshift code; build the current source we have in the upstream repo for testing purpose")
@click.option("--force", is_flag=True,
              help="(For named assemblies) Rebuild even if a build already exists")
@pass_runtime
@click_coroutine
async def build_microshift(runtime: Runtime, ocp_build_data_url: str, group: str, assembly: str, payloads: Tuple[str, ...],
                           no_rebase: bool, force: bool):
    pipeline = BuildMicroShiftPipeline(runtime=runtime, group=group, assembly=assembly, payloads=payloads,
                                       no_rebase=no_rebase, force=force, ocp_build_data_url=ocp_build_data_url)
    await pipeline.run()
