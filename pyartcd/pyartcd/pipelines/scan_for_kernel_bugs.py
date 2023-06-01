
import os
import traceback
from typing import Optional, Tuple

import click

from pyartcd import constants, exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


class ScanForKernelBugsPipeline:
    def __init__(self, runtime: Runtime, data_path: Optional[str], group: str,
                 reconcile: bool, trackers: Tuple[str, ...]) -> None:
        self._runtime = runtime
        self.data_path = data_path or runtime.config.get("build_config", {}).get("ocp_build_data_url")
        self.group = group
        self.reconcile = reconcile
        self.trackers = list(trackers)
        self._logger = runtime.logger

        self._working_dir = self._runtime.working_dir
        self._elliott_working_dir = self._working_dir / "elliott-working"
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self._elliott_working_dir)
        if self.data_path:
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = self.data_path

    async def run(self):
        logger = self._logger
        slack_client = self._runtime.new_slack_client()
        slack_client.bind_channel(self.group)
        try:
            logger.info("Scanning KMAINT trackers for kernel bugs...")
            await self._clone_kernel_bugs()
            logger.info("Moving cloned Jira issues...")
            await self._move_kernel_bugs()
            logger.info("Done")
        except Exception as err:
            error_message = f"Error scanning for kernel bugs: {err}\n {traceback.format_exc()}"
            logger.error(error_message)
            await slack_client.say(f":warning: {error_message}")
            raise

    async def _clone_kernel_bugs(self):
        """ Run `elliott find-bugs:kernel --clone`
        :return: a dict containing which packages have been tagged and untagged
        """
        cmd = [
            "elliott",
            "--group", self.group,
            "--assembly", "stream",
            "find-bugs:kernel",
            "--clone",
            "--comment",
        ]
        if self.reconcile:
            cmd.append("--reconcile")
        if self.trackers:
            cmd.extend([f"--tracker={tracker}" for tracker in self.trackers])
        if self._runtime.dry_run:
            cmd.append("--dry-run")
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars)

    async def _move_kernel_bugs(self):
        """ Run `elliott find-bugs:kernel-clones --move`
        :return: a dict containing which packages have been tagged and untagged
        """
        cmd = [
            "elliott",
            "--group", self.group,
            "--assembly", "stream",
            "find-bugs:kernel-clones",
            "--move",
            "--comment",
        ]
        if self.trackers:
            cmd.extend([f"--tracker={tracker}" for tracker in self.trackers])
        if self._runtime.dry_run:
            cmd.append("--dry-run")
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars)


@cli.command("scan-for-kernel-bugs", short_help="Scan for kernel bugs")
@click.option("--data-path", metavar='BUILD_DATA', default=None,
              help=f"Git repo or directory containing groups metadata e.g. {constants.OCP_BUILD_DATA_URL}")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.12")
@click.option("--reconcile",
              is_flag=True,
              help="Update summary, description, etc for already cloned Jira bugs")
@click.option("--tracker", "trackers", metavar='JIRA_KEY', multiple=True,
              help="Find kernel bugs by the specified KMAINT tracker JIRA_KEY")
@pass_runtime
@click_coroutine
async def scan_for_kernel_bugs_cli(runtime: Runtime, data_path: Optional[str], group: str,
                                   reconcile: bool, trackers: Tuple[str, ...]):
    """ This job scans KMAINT Jira tracker for kernel bugs in Bugzilla, clones them into OCP Jira,
    and move their statuses.
    """
    pipeline = ScanForKernelBugsPipeline(runtime=runtime, data_path=data_path, group=group,
                                         reconcile=reconcile, trackers=trackers)
    await pipeline.run()
