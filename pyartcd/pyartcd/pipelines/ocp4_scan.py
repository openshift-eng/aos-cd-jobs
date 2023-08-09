import os
from typing import Optional
import yaml

import click
from aioredlock import LockError

from pyartcd import constants, exectools, util, locks
from pyartcd import jenkins
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.locks import Lock
from pyartcd.runtime import Runtime


class Ocp4ScanPipeline:

    def __init__(self, runtime: Runtime, version: str, data_path: Optional[str] = None):
        self.runtime = runtime
        self.version = version
        self.data_path = data_path or constants.OCP_BUILD_DATA_URL  # in case we will make it a parameter
        self.logger = runtime.logger
        self.rhcos_changed = False
        self.rhcos_inconsistent = False
        self.inconsistent_rhcos_rpms = None
        self.changes = {}
        self._doozer_working = self.runtime.working_dir / "doozer_working"

    async def run(self):
        # Check if automation is frozen for current group
        if not await util.is_build_permitted(self.version, doozer_working=self._doozer_working):
            self.logger.info('Skipping this build as it\'s not permitted')
            return

        self.logger.info('Building: %s', self.version)

        # KUBECONFIG env var must be defined in order to scan sources
        if not os.getenv('KUBECONFIG'):
            raise RuntimeError('Environment variable KUBECONFIG must be defined')

        # Check for RHCOS changes and inconsistencies
        # Running these two commands sequentially (instead of using asyncio.gather) to avoid file system conflicts
        await self._get_changes()
        await self._rhcos_inconsistent()

        # Handle source changes, if any
        if self.changes.get('rpms', None) or self.changes.get('images', None):
            self.logger.info('Detected at least one updated RPM or image')

            if self.runtime.dry_run:
                self.logger.info('Would have triggered a %s ocp4 build', self.version)
                return

            # Trigger ocp4
            self.logger.info('Triggering a %s ocp4 build', self.version)
            jenkins.start_ocp4(
                build_version=self.version,
                assembly='stream',
                blocking=False,
                rpm_list=self.changes.get('rpms', []),
                image_list=self.changes.get('images', []),
            )

        elif self.rhcos_inconsistent:
            self.logger.info('Detected inconsistent RHCOS RPMs:\n%s', self.inconsistent_rhcos_rpms)

            if self.runtime.dry_run:
                self.logger.info('Would have triggered a %s RHCOS build', self.version)
                return

            # Inconsistency probably means partial failure and we would like to retry.
            # but don't kick off more if already in progress.
            self.logger.info('Triggering a %s RHCOS build for consistency', self.version)
            jenkins.start_rhcos(build_version=self.version, new_build=True, blocking=False)

        elif self.rhcos_changed:
            self.logger.info('Detected at least one updated RHCOS')

            if self.runtime.dry_run:
                self.logger.info('Would have triggered a %s build-sync build', self.version)
                return

            self.logger.info('Triggering a %s build-sync', self.version)
            jenkins.start_build_sync(
                build_version=self.version,
                assembly="stream",
                blocking=False
            )

    async def _get_changes(self):
        """
        Check for changes by calling doozer config:scan-sources
        Changed rpms, images or rhcos are recorded in self.changes
        self.rhcos_changed is also updated accordingly
        """

        # Run doozer scan-sources
        cmd = f'doozer --data-path={self.data_path} --assembly stream --working-dir={self._doozer_working} --group=openshift-{self.version} ' \
              f'config:scan-sources --yaml --ci-kubeconfig {os.environ["KUBECONFIG"]}'
        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None)
        self.logger.info('scan-sources output for openshift-%s:\n%s', self.version, out)

        yaml_data = yaml.safe_load(out)
        changes = util.get_changes(yaml_data)
        if changes:
            self.logger.info('Detected source changes:\n%s', yaml.safe_dump(changes))
        else:
            self.logger.info('No changes detected in RPMs, images or RHCOS')

        # Check for RHCOS changes
        if changes.get('rhcos', None):
            self.rhcos_changed = True
        else:
            self.rhcos_changed = False

        self.changes = changes

    async def _rhcos_inconsistent(self):
        """
        Check for RHCOS inconsistencies by calling doozer inspect:stream INCONSISTENT_RHCOS_RPMS
        """

        cmd = f'doozer --data-path={self.data_path} --assembly stream --working-dir {self._doozer_working} --group openshift-{self.version} ' \
              f'inspect:stream INCONSISTENT_RHCOS_RPMS --strict'
        try:
            _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None)
            self.logger.info(out)
            self.rhcos_inconsistent = False
        except ChildProcessError as e:
            self.rhcos_inconsistent = True
            self.inconsistent_rhcos_rpms = e


@cli.command('ocp4-scan')
@click.option('--version', required=True, help='OCP version to scan')
@pass_runtime
@click_coroutine
async def ocp4_scan(runtime: Runtime, version: str):
    # Create a Lock manager instance
    lock = Lock.GITHUB_ACTIVITY
    lock_manager = locks.LockManager.from_lock(lock)
    lock_name = lock.value.format(version=version)

    try:
        # Skip the build if already locked
        if await lock_manager.is_locked(lock_name):
            runtime.logger.info('Looks like there is another build ongoing for %s -- skipping for this run', version)
            await lock_manager.destroy()
            return

        async with await lock_manager.lock(lock_name):
            await Ocp4ScanPipeline(runtime, version).run()

    except LockError as e:
        runtime.logger.error('Failed acquiring lock %s: %s', lock_name, e)
        raise
