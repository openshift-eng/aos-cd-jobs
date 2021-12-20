import os
import re
from typing import Iterable, Tuple
from urllib.parse import quote, urljoin, urlparse

import click
from pyartcd import constants, exectools, util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


class TarballSourcesPipeline:
    def __init__(self, runtime: Runtime, group: str, assembly: str, components: Iterable[str], advisories: Iterable[int]) -> None:
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.components = list(components)
        self.advisories = list(advisories)

        self._jira_client = runtime.new_jira_client()

        # sets environment variables for Elliott and Doozer
        self._ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self.runtime.working_dir / "elliott-working")
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.runtime.working_dir / "doozer-working")
        if self._ocp_build_data_url:
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = self._ocp_build_data_url
            self._doozer_env_vars["DOOZER_DATA_PATH"] = self._ocp_build_data_url

    async def run(self):
        advisories = self.advisories
        if not advisories:
            # use advisory numbers from ocp-build-data
            self.runtime.logger.info("Loading advisory numbers from group config...")
            group_config = await util.load_group_config(self.group, self.assembly, self._doozer_env_vars)
            advisories = list(group_config.get("advisories", {}).values())
        if not advisories:
            raise ValueError("No advisories to look up.")
        self.runtime.logger.info("Creating tarball sources for advisories %s", advisories)
        source_directory = f"{self.runtime.working_dir}/container-sources/"
        tarball_files = await self._create_tarball_sources(advisories, source_directory)
        self.runtime.logger.info("Copying to rcm-guest")
        await self._copy_to_rcm_guest(source_directory)
        self.runtime.logger.info("Creating JIRA")
        new_issue = self._create_jira(advisories, tarball_files)
        if self.runtime.dry_run:
            new_issue_key = "FAKE-123"
            self.runtime.logger.warning("[DRY RUN] A JIRA ticket should have been created. Using fake JIRA issue key %s", new_issue_key)
        else:
            new_issue_key = new_issue.key
        new_issue_url = urljoin(f"{self.runtime.config['jira']['url']}/browse/", quote(new_issue_key))
        print(f"Created JIRA ticket: {new_issue_url}")

    async def _create_tarball_sources(self, advisories: Iterable[int], source_directory: str):
        cmd = ["elliott", "--debug", f"--group={self.group}", f"--assembly={self.assembly}", "tarball-sources", "create", "--force", f"--out-dir={source_directory}"]
        for c in self.components:
            cmd.append(f"--component={c}")
        for ad in advisories:
            cmd.append(f"{ad}")
        _, out, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, capture_stderr=False)
        # look for lines like `RHEL-7-OSE-4.2/${advisory}/release/logging-fluentd-container-v4.2.26-202003230335.tar.gz`
        pattern = re.compile(r"^(.+\.tar\.gz)$")
        tarball_files = [line for line in out.splitlines() if pattern.match(line)]
        return tarball_files

    async def _copy_to_rcm_guest(self, source_directory: str):
        remote = f"{constants.TARBALL_SOURCES_REMOTE_HOST}:{constants.TARBALL_SOURCES_REMOTE_BASE_DIR}"
        cmd = ["rsync", "-avz", "--no-perms", "--no-owner", "--no-group", f"{source_directory}", f"{remote}"]
        if self.runtime.dry_run:
            self.runtime.logger.warning("[DRY RUN] Would have run: %s", cmd)
            return
        await exectools.cmd_assert_async(cmd)

    def _create_jira(self, advisories: Iterable[int], tarball_files: Iterable[str]):
        summary = "OCP Tarball sources"
        description = f"""
The OpenShift ART team needs to provide sources for `{self.components}` in advisories {[advisory for advisory in advisories]}

The following sources are uploaded to {urlparse(constants.TARBALL_SOURCES_REMOTE_HOST).hostname}:

{os.linesep.join(map(lambda f: f"{constants.TARBALL_SOURCES_REMOTE_HOST}:{constants.TARBALL_SOURCES_REMOTE_BASE_DIR}/{f}", tarball_files))}

Attaching source tarballs to be published on ftp.redhat.com as in https://projects.engineering.redhat.com/browse/RCMTEMPL-6549
""".strip()
        if self.runtime.dry_run:
            self.runtime.logger.warning("[DRY RUN] Would have created JIRA ticket to CLOUDDST: summary=%s, description=%s", summary, description)
            return None
        new_issue = self._jira_client.create_issue("CLOUDDST", "Ticket", summary, description)
        return new_issue


@cli.command("tarball-sources")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly. e.g. 4.9.1")
@click.option("--advisory", "-a", "advisories", metavar="ADVISORY", type=int, multiple=True,
              help="Advisory number. If unspecified, use the advisory number from ocp-build-data.")
@pass_runtime
@click_coroutine
async def tarball_sources(runtime: Runtime, group: str, assembly: str, advisories: Tuple[int, ...]):
    COMPONENTS = ["logging-fluentd-container"]
    pipeline = TarballSourcesPipeline(runtime, group, assembly, COMPONENTS, advisories)
    await pipeline.run()
