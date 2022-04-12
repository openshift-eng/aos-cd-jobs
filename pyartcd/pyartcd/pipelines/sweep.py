import time
from enum import Enum
import sys

import click

from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd.exectools import cmd_assert_async, cmd_gather_async
from pyartcd.runtime import Runtime
from pyartcd.util import kinit

DOOZER_BIN = 'doozer'
ELLIOTT_BIN = 'elliott'
MAX_RETRIES = 3
ONE_MINUTE = 1000


class StatusCode(Enum):
    SUCCESS = 0,
    BUILD_NOT_PERMITTED = 1,
    RUNTIME_ERROR = 2,
    DRY_RUN = 3


class SweepBugsPipeline:
    def __init__(self, runtime: Runtime, version: str, attach_bugs) -> None:
        self.runtime = runtime
        self.version = version
        self.attach_bugs = attach_bugs
        self.logger = runtime.logger

    async def run(self):
        # Check Elliott version
        try:
            await cmd_assert_async(f'{ELLIOTT_BIN} --version')
        except ChildProcessError:
            sys.exit(StatusCode.RUNTIME_ERROR.value)

        # Initialize kerberos credentials
        try:
            await kinit()
        except ChildProcessError:
            self.logger.error('Failed initializing Kerberos credentials')
            sys.exit(StatusCode.RUNTIME_ERROR.value)

        # If automation is frozen, return
        if not await self._is_build_permitted():
            self.logger.warning('Automation is frozen, current build is not permitted')
            sys.exit(StatusCode.BUILD_NOT_PERMITTED.value)
        self.logger.info('Automation not frozen, building')

        # Sweep bugs
        await self._sweep_bugs()

    async def _sweep_bugs(self):
        cmd = self._elliott_find_bugs_cmd()

        # Execute elliott find-bugs
        success = False
        for i in range(MAX_RETRIES):
            errcode = await cmd_assert_async(cmd, check=False)
            if errcode:
                # Elliott failed, log error and retry
                self.logger.warning('Error attaching bugs to advisories (will retry a few times)')
                time.sleep(ONE_MINUTE)
            else:
                # All good, exit the loop
                success = True
                break

        # If it failed for 3 times, exit with pain
        if not success:
            self.logger.error('Elliott find-bugs failed for 3 times! Aborting')
            sys.exit(StatusCode.RUNTIME_ERROR.value)

    def _elliott_find_bugs_cmd(self) -> list:
        cmd = [
            ELLIOTT_BIN,
            f'--group=openshift-{self.version}',
            'find-bugs',
        ]

        if self.attach_bugs:
            self.logger.info('Attaching MODIFIED, ON_QA, and VERIFIED bugs to default advisories')
            cmd.extend([
                '--mode=sweep',
                '--cve-trackers',
                '--status=MODIFIED',
                '--status=ON_QA',
                '--status=VERIFIED',
                '--into-default-advisories',
            ])
        else:
            self.logger.info('Changing MODIFIED bugs to ON_QA')
            cmd.extend([
                '--cve-trackers',
                '--mode=qe'
            ])

        if self.runtime.dry_run:
            cmd.append('--dry-run')

        return cmd

    async def _is_build_permitted(self) -> bool:
        """
        This job is never run directly by humans, so it is considered
        permitted only when freeze_automation is set to False
        """

        cmd = [
            DOOZER_BIN,
            f'--group=openshift-{self.version}',
            'config:read-group',
            '--default=no',
            'freeze_automation'
        ]
        self.logger.info('Executing command: %s', cmd)
        _, out, _ = await cmd_gather_async(cmd)
        return out.strip() == 'False'


@cli.command('sweep-bugs')
@click.option('--version', required=True, help='OCP version')
@click.option('--attach-bugs', is_flag=True, default=False,
              help='Slack channel to be notified for failures')
@pass_runtime
@click_coroutine
async def sweep_bugs(runtime: Runtime, version: str, attach_bugs: bool):
    pipeline = SweepBugsPipeline(runtime, version, attach_bugs)
    await pipeline.run()
    pipeline.logger.debug('Pipeline completed')

    if runtime.dry_run:
        sys.exit(StatusCode.DRY_RUN.value)
    sys.exit(StatusCode.SUCCESS.value)
