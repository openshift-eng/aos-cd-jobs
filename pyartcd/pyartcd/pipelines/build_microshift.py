import logging
import os
import re
import shutil
from collections import namedtuple
from datetime import datetime
from pathlib import Path
import traceback
from typing import Dict, Iterable, List, Optional, Tuple

import click
import yaml
from doozerlib.assembly import AssemblyTypes
from pyartcd import exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from pyartcd.util import (get_assembly_type, get_release_name,
                          isolate_el_version_in_release, load_group_config, load_releases_config)
from semver import VersionInfo

PlashetBuildResult = namedtuple("PlashetBuildResult", ("repo_name", "local_dir", "remote_url"))


class BuildMicroShiftPipeline:
    """ Rebase and build MicroShift for an assembly """

    SUPPORTED_ASSEMBLY_TYPES = {AssemblyTypes.STANDARD, AssemblyTypes.CANDIDATE, AssemblyTypes.PREVIEW}

    def __init__(self, runtime: Runtime, group: str, assembly: str,
                 ocp_build_data_url: str, logger: Optional[logging.Logger] = None):
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self._logger = logger or runtime.logger
        self._slack_client = self.runtime.new_slack_client()

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
        if not match:
            raise ValueError(f"Invalid group name: {group}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.runtime.working_dir / "doozer-working")

        if not ocp_build_data_url:
            ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        if ocp_build_data_url:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = ocp_build_data_url

    async def run(self):
        self._slack_client.bind_channel(self.group)
        slack_response = await self._slack_client.say(f":construction: Build microshift for assembly {self.assembly} :construction:")
        slack_thread = slack_response["message"]["ts"]

        try:
            await load_group_config(self.group, self.assembly, env=self._doozer_env_vars)
            releases_config = await load_releases_config(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"], "ocp-build-data"))
            assembly_type = get_assembly_type(releases_config, self.assembly)
            if assembly_type not in self.SUPPORTED_ASSEMBLY_TYPES:
                raise ValueError(f"Building MicroShift for assembly type {assembly_type.value} is not currently supported.")
            release_name = get_release_name(assembly_type, self.group, self.assembly, None)

            # Rebases and builds microshift
            version, release = self.generate_microshift_version_release(release_name)
            nvrs = await self._rebase_and_build_rpm(version, release)

            # https://mirror.openshift.com/pockets/microshift/4.10-el8/stream/x86_64/os/

            # Prints example schema
            click.secho("Build completes. Please update the assembly schema in releases.yaml to pin the following NVR(s) to the assembly:\n", fg="green")
            for nvr in nvrs:
                click.secho(f"\t{nvr}", fg="green")
            example_schema = yaml.safe_dump(self._generate_example_schema(nvrs))
            click.secho(f"\nExample schema:\n\n{example_schema}", fg="green")

            # Sends a slack message
            # TODO: We might want this job to auto create a PR to ocp-build-data.
            await self._slack_client.say(f"Hi @release-artists , microshift for assembly {self.assembly} has been successfully built.", slack_thread)
            await self._slack_client.say(f"Please create a PR to pin the build:\n```\n{example_schema}\n```", slack_thread)
        except Exception as err:
            error_message = f"Error building microshift: {err}\n {traceback.format_exc()}"
            self._logger.error(error_message)
            await self._slack_client.say(error_message, slack_thread)
            raise

    @staticmethod
    def generate_microshift_version_release(ocp_version: str, timestamp: Optional[str] = None):
        """ Generate version and release strings for microshift rpm.
        Example version-releases:
        - 4.12.42-202210011234
        - 4.13.0~rc.4-202210011234
        """
        if not timestamp:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
        release_version = VersionInfo.parse(ocp_version)
        version = f"{release_version.major}.{release_version.minor}.{release_version.patch}"
        if release_version.prerelease is not None:
            version += f"~{release_version.prerelease}"
        release = f"{timestamp}.p?"
        return version, release

    async def _rebase_and_build_rpm(self, version, release: str) -> List[str]:
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
        await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        if self.runtime.dry_run:
            return [f"microshift-{version}-{release.replace('.p?', '.p0')}.el8"]

        # parse record.log
        with open(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / "record.log", "r") as file:
            record_log = parse_record_log(file)
            return record_log["build_rpm"][-1]["nvrs"].split(",")

    def _generate_example_schema(self, nvrs: List[str]) -> Dict:
        """ Generate an example assembly definition to pin the specified NVRs.
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
        member_type = "rpms"
        dg_key = "microshift"
        for nvr in nvrs:
            el_version = isolate_el_version_in_release(nvr)
            assert el_version is not None
            is_entry[f"el{el_version}"] = nvr
        schema = {
            "releases": {
                self.assembly: {
                    "assembly": {
                        "members": {
                            member_type: [
                                {
                                    "distgit_key": dg_key,
                                    "metadata": {
                                        "is": is_entry
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        return schema


@cli.command("build-microshift")
@click.option("--ocp-build-data-url", metavar='BUILD_DATA', default=None,
              help="Git repo or directory containing groups metadata e.g. https://github.com/openshift/ocp-build-data")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly to rebase & build for. e.g. 4.9.1")
@pass_runtime
@click_coroutine
async def rebuild(runtime: Runtime, ocp_build_data_url: str, group: str, assembly: str):
    pipeline = BuildMicroShiftPipeline(runtime=runtime, group=group, assembly=assembly, ocp_build_data_url=ocp_build_data_url)
    await pipeline.run()
