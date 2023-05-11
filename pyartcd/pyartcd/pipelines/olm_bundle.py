import click
from aioredlock import LockError

from pyartcd import constants, exectools
from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd import locks
from pyartcd.runtime import Runtime


@cli.command('olm-bundle')
@click.option('--version', required=True, help='OCP version')
@click.option('--assembly', required=True, help='Assembly name')
@click.option('--data-path', required=False, default=constants.OCP_BUILD_DATA_URL,
              help='ocp-build-data fork to use (e.g. assembly definition in your own fork)')
@click.option('--data-gitref', required=False,
              help='(Optional) Doozer data path git [branch / tag / sha] to use')
@click.option('--nvrs', required=False,
              help='(Optional) List **only** the operator NVRs you want to build bundles for, everything else '
                   'gets ignored. The operators should not be mode:disabled/wip in ocp-build-data')
@click.option('--only', required=False,
              help='(Optional) List **only** the operators you want to build, everything else gets ignored.\n'
                   'Format: Comma and/or space separated list of brew packages (e.g.: cluster-nfd-operator-container)\n'
                   'Leave empty to build all (except EXCLUDE, if defined)')
@click.option('--exclude', required=False,
              help='(Optional) List the operators you **don\'t** want to build, everything else gets built.\n'
                   'Format: Comma and/or space separated list of brew packages (e.g.: cluster-nfd-operator-container)\n'
                   'Leave empty to build all (or ONLY, if defined)')
@click.option('--force', is_flag=True,
              help='Rebuild bundle containers, even if they already exist for given operator NVRs')
@pass_runtime
@click_coroutine
async def olm_bundle(runtime: Runtime, version: str, assembly: str, data_path: str, data_gitref: str,
                     nvrs: str, only: bool, exclude: str, force: bool):
    # Create Doozer invocation
    cmd = [
        'doozer',
        f'--assembly={assembly}',
        '--working-dir=doozer_working',
        f'--group=openshift-{version}@{data_gitref}' if data_gitref else f'--group=openshift-{version}',
        f'--data-path={data_path}'
    ]
    if only:
        cmd.append(f'--images={only}')
    if exclude:
        cmd.append(f'--exclude={exclude}')
    cmd.append('olm-bundle:rebase-and-build')
    if force:
        cmd.append('--force')
    if runtime.dry_run:
        cmd.append('--dry-run')
    cmd.append('--')
    cmd.extend(nvrs.split(','))

    # Create a Lock manager instance
    lock_policy = locks.LOCK_POLICY['olm_bundle']
    lock_manager = locks.new_lock_manager(
        internal_lock_timeout=lock_policy['lock_timeout'],
        retry_count=lock_policy['retry_count'],
        retry_delay_min=lock_policy['retry_delay_min']
    )

    # Try to acquire olm-bundle lock for build version
    lock_name = f'olm_bundle-{version}'
    try:
        async with await lock_manager.lock(lock_name):
            runtime.logger.info('Running command: %s', cmd)
            await exectools.cmd_assert_async(cmd)

    except LockError as e:
        runtime.logger.error('Failed acquiring lock %s: %s', lock_name, e)
        raise

    finally:
        await lock_manager.destroy()
