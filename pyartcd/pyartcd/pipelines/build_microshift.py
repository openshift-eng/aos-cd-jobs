import logging
import os
import re
import traceback
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import click
import yaml
from doozerlib.assembly import AssemblyTypes
from ghapi.all import GhApi
from pyartcd import exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.git import GitRepository
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from pyartcd.util import (get_assembly_type, get_release_name,
                          isolate_el_version_in_release, load_group_config,
                          load_releases_config)
from semver import VersionInfo
from ruamel.yaml import YAML


yaml = YAML(typ="rt")


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
        self._working_dir = self.runtime.working_dir.absolute()

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
        if not match:
            raise ValueError(f"Invalid group name: {group}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._working_dir / "doozer-working")

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

            # Create a PR to pin microshift build
            pr = await self._create_or_update_pull_request(nvrs)

            # Sends a slack message
            message = f"Hi @release-artists , microshift for assembly {self.assembly} has been successfully built."
            if pr:
                message += f"\nA PR to update the assembly definition has been created/updated: {pr.html_url}"
                message += "\nTo publish the build to the pocket, run update-microshift-pocket job after the PR is merged."
            await self._slack_client.say(message, slack_thread)
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

    async def _create_or_update_pull_request(self, nvrs: List[str]):
        self._logger.info("Creating ocp-build-data PR...")
        # Clone ocp-build-data
        build_data_path = self._working_dir / "ocp-build-data-push"
        build_data = GitRepository(build_data_path, dry_run=self.runtime.dry_run)
        ocp_build_data_repo_push_url = self.runtime.config["build_config"]["ocp_build_data_repo_push_url"]
        await build_data.setup(ocp_build_data_repo_push_url)
        branch = f"auto-pin-microshift-{self.group}-{self.assembly}"
        await build_data.fetch_switch_branch(branch, self.group)
        # Make changes
        releases_yaml_path = build_data_path / "releases.yml"
        releases_yaml = yaml.load(releases_yaml_path)
        self._pin_nvrs(nvrs, releases_yaml)
        yaml.dump(releases_yaml, releases_yaml_path)
        # Create a PR
        title = f"Pin microshift build for {self.group} {self.assembly}"
        body = f"Created by job run {self.runtime.get_job_run_url()}"
        match = re.search(r"github\.com[:/](.+)/(.+)(?:.git)?", ocp_build_data_repo_push_url)
        if not match:
            raise ValueError(f"Couldn't create a pull request: {ocp_build_data_repo_push_url} is not a valid github repo")
        head = f"{match[1]}:{branch}"
        base = self.group
        if self.runtime.dry_run:
            self._logger.warning("[DRY RUN] Would have created pull-request with head '%s', base '%s' title '%s', body '%s'", head, base, title, body)
            d = {"html_url": "https://github.example.com/foo/bar/pull/1234", "number": 1234}
            result = namedtuple('pull_request', d.keys())(*d.values())
            return result
        pushed = await build_data.commit_push(f"{title}\n{body}")
        result = None
        if pushed:
            github_token = os.environ.get('GITHUB_TOKEN')
            if not github_token:
                raise ValueError("GITHUB_TOKEN environment variable is required to create a pull request")
            owner = "openshift"
            repo = "ocp-build-data"
            api = GhApi(owner=owner, repo=repo, token=github_token)
            existing_prs = api.pulls.list(state="open", base=base, head=head)
            if not existing_prs.items:
                result = api.pulls.create(head=head, base=base, title=title, body=body, maintainer_can_modify=True)
            else:
                pull_number = existing_prs.items[0].number
                result = api.pulls.update(pull_number=pull_number, title=title, body=body)
        else:
            self._logger.warning("PR is not created: Nothing to commit.")
        return result


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
