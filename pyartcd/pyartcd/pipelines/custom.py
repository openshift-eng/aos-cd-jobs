import click
from aioredlock import LockError

from pyartcd import constants, exectools, locks, plashets, util
from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd.runtime import Runtime

DOOZER_WORKING = "doozer_working"


@cli.group("custom", short_help="Run component builds in ways other jobs can't")
def custom():
    pass


@custom.command('build-rpms')
@click.option('--version', required=True, help='Full OCP version, e.g. 4.14-202304181947.p?')
@click.option("--rpms", required=False, default='',
              help="Comma-separated list of RPM distgits to build. Empty for all")
@click.option("--data-path", required=True, default=constants.OCP_BUILD_DATA_URL,
              help="ocp-build-data fork to use (e.g. assembly definition in your own fork)")
@click.option("--data-gitref", required=False, default='',
              help="(Optional) Doozer data path git [branch / tag / sha] to use")
@click.option('--scratch', is_flag=True,
              help='Run scratch builds (only unrelated images, no children)')
@pass_runtime
@click_coroutine
async def build_rpms(runtime: Runtime, version: str, rpms: str, data_path: str, data_gitref: str, scratch: bool):
    stream_version, release_version = version.split('-')  # e.g. 4.14 from 4.14-202304181947.p?

    group_param = f'openshift-{stream_version}'
    if data_gitref:
        group_param = f'{group_param}@{data_gitref}'

    cmd = ['doozer',
           f'--working-dir={DOOZER_WORKING}',
           f'--data-path={data_path}',
           f'--group={group_param}'
           ]

    if rpms:
        runtime.logger.info('Building RPMs: %s', rpms)
        cmd.append(f'--rpms={rpms}')
    else:
        runtime.logger.info('Building all RPMs')

    cmd.extend([
        'rpms:rebase-and-build',
        f'--version={stream_version}',
        f'--release={release_version}'
    ])

    if scratch:
        cmd.append('--scratch')

    try:
        await exectools.cmd_assert_async(cmd)
    except ChildProcessError:
        runtime.logger.error('Failed building RPMs for %s', stream_version)
        raise


@custom.command('update-repos')
@click.option('--version', required=True, help='Full OCP version, e.g. 4.14-202304181947.p?')
@click.option('--assembly', required=True, help='The name of an assembly to rebase & build for.')
@click.option("--data-path", required=False, default=constants.OCP_BUILD_DATA_URL,
              help="ocp-build-data fork to use (e.g. assembly definition in your own fork)")
@click.option("--data-gitref", required=False, default='',
              help="(Optional) Doozer data path git [branch / tag / sha] to use")
@pass_runtime
@click_coroutine
async def update_repos(runtime: Runtime, version: str, assembly: str, data_path: str, data_gitref: str):
    stream_version, release_version = version.split('-')  # e.g. 4.14 from 4.14-202304181947.p?

    # Create a Lock manager instance
    lock_policy = locks.LOCK_POLICY['compose']
    lock_manager = locks.new_lock_manager(
        internal_lock_timeout=lock_policy['lock_timeout'],
        retry_count=lock_policy['retry_count'],
        retry_delay_min=lock_policy['retry_delay_min']
    )
    lock_name = f'compose-lock-{stream_version}'

    # Update repos
    try:
        async with await lock_manager.lock(lock_name):
            await plashets.build_plashets(
                stream_version, release_version, assembly=assembly, data_path=data_path, data_gitref=data_gitref)

            # If plashets were rebuilt during automation freeze, notify via Slack (only for OCP >= 4.y)
            if int(stream_version.split('.')[0]) >= 4:
                automation_state = await util.get_freeze_automation(stream_version, data_path, DOOZER_WORKING)
                if automation_state in ['scheduled', 'yes', 'True']:
                    slack_client = runtime.new_slack_client()
                    slack_client.bind_channel(f'openshift-{stream_version}')
                    await slack_client.say('*:alert: custom build repositories ran during automation freeze*')

    except ChildProcessError:
        runtime.logger.error('Failed updating repos for %s', stream_version)
        raise

    except LockError as e:
        runtime.logger.error('Failed acquiring lock %s: %s', lock_name, e)
        raise

    finally:
        await lock_manager.destroy()
