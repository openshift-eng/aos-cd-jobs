
import json
import os
import traceback
from typing import Optional

import click

from pyartcd import constants, exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


class TagRPMsPipeline:
    def __init__(self, runtime: Runtime, data_path: Optional[str], group: str) -> None:
        self._runtime = runtime
        self.data_path = data_path or runtime.config.get("build_config", {}).get("ocp_build_data_url")
        self.group = group

        self._working_dir = self._runtime.working_dir
        self._doozer_working_dir = self._working_dir / "doozer-working"
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._doozer_working_dir)
        if self.data_path:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = self.data_path

    async def run(self):
        logger = self._runtime.logger
        slack_client = self._runtime.new_slack_client()
        slack_client.bind_channel(self.group)
        try:
            logger.info("Running doozer config:tag-rpms for %s...", self.group)
            report = await self.tag_rpms()
            untagged = False
            tagged = False
            message = ""
            if report["untagged"]:
                for tag, nvrs in report["untagged"].items():
                    if not nvrs:
                        continue
                    untagged = True
                    message += f"{len(nvrs)} builds have been untagged from Brew tag {tag}:\n"
                    for nvr in nvrs:
                        message += f"\t{nvr}\n"
                if untagged:
                    message += "Builds were untagged because they were tagged into the stop-ship tags.\n\n"
            if report["tagged"]:
                for tag, nvrs in report["tagged"].items():
                    if not nvrs:
                        continue
                    tagged = True
                    message += f"{len(nvrs)} builds have been tagged into Brew tag {tag}:\n"
                    for nvr in nvrs:
                        message += f"\t{nvr}\n"
                    message += f"To revert, run `brew untag {tag} {' '.join(nvrs)}`.\n"
                if tagged:
                    message += "If you untag a build manually, it will not be re-tagged by this job again.\n\n"
            if untagged or tagged:  # Don't spam release-artists if nothing changed
                await slack_client.say(f":white_check_mark: Hi @release-artists ,\n{message}")
        except Exception as err:
            error_message = f"Error running tag-rpms: {err}\n {traceback.format_exc()}"
            logger.error(error_message)
            await slack_client.say(f":warning: {error_message}")
            raise

    async def tag_rpms(self):
        """ run doozer config:tag-rpms
        :return: a dict containing which packages have been tagged and untagged
        """
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", "stream",
            "config:tag-rpms",
            "--json",
        ]
        if self._runtime.dry_run:
            cmd.append("--dry-run")
        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=self._doozer_env_vars)
        # example out:
        # {"untagged": {"test-target-tag": ["bar-1.0.0-1"]}, "tagged": {"test-target-tag": ["bar-1.0.2-1", "foo-1.0.1-1"]}}
        return json.loads(out)


@cli.command("tag-rpms", short_help="Tag and untag rpms for rpm delivery")
@click.option("--data-path", metavar='BUILD_DATA', default=None,
              help=f"Git repo or directory containing groups metadata e.g. {constants.OCP_BUILD_DATA_URL}")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.12")
@pass_runtime
@click_coroutine
async def tag_rpms_cli(runtime: Runtime, data_path: Optional[str], group: str):
    pipeline = TagRPMsPipeline(runtime=runtime, data_path=data_path, group=group)
    await pipeline.run()
