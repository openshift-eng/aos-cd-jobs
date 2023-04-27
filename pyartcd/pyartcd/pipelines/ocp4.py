
import traceback

import click
from aioredlock import LockError

from pyartcd import locks, util, plashets
from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd.runtime import Runtime
from pyartcd.s3 import sync_repo_to_s3_mirror

# Doozer working dir
DOOZER_WORKING = 'doozer_working'


@cli.command("ocp4:build-compose",
             help="If any RPMs have changed, create multiple yum repos (one for each arch) based on -candidate tags"
                  "those repos can be signed (release state) or unsigned (pre-release state)")
@click.option('--version', required=True, help='Full OCP version, e.g. 4.14-202304181947.p?')
@click.option('--assembly', required=True, help='The name of an assembly to rebase & build for')
@click.option('--build-rpms', is_flag=True, help='True if RPMs should be built')
@pass_runtime
@click_coroutine
async def build_compose(runtime: Runtime, version: str, assembly: str, build_rpms: bool):
    stream_version, release_version = version.split('-')  # e.g. (4.14, 202304181947.p?) from 4.14-202304181947.p?

    # Create a Lock manager instance
    lock_policy = locks.LOCK_POLICY['compose']
    lock_manager = locks.new_lock_manager(
        internal_lock_timeout=lock_policy['lock_timeout'],
        retry_count=lock_policy['retry_count'],
        retry_delay_min=lock_policy['retry_delay_min']
    )
    lock_name = f'compose-lock-{stream_version}'

    # Build compose
    try:
        async with await lock_manager.lock(lock_name):
            automation_state: str = await util.get_freeze_automation(stream_version)
            runtime.logger.info('Automation state for %s: %s', stream_version, automation_state)

            # - If automation is not frozen, go ahead
            # - If automation is "scheduled" and job was triggered by human
            #   and there were no RPMs in the build plan: Do not build compose
            # - If automation is "scheduled" and job was triggered by human
            #   and there were RPMs in the build plan: Build compose, and warn
            if automation_state in ['scheduled', 'yes', 'True'] or \
                    (automation_state in ['scheduled', 'weekdays'] and build_rpms):
                mirror_plashet = await plashets.build_plashets(
                    stream_version, release_version, assembly=assembly, dry_run=runtime.dry_run)
                click.echo(mirror_plashet)
            else:
                runtime.logger.info('Skipping compose build')

            if automation_state == 'scheduled' and build_rpms:
                slack_client = runtime.new_slack_client()
                slack_client.bind_channel(f'openshift-{stream_version}')
                await slack_client.say(
                    "*:alert: ocp4 build compose ran during automation freeze*\n"
                    "There were RPMs in the build plan that forced build compose during automation freeze."
                )

    except ChildProcessError as e:
        error_msg = f'Failed building compose: {e}'
        runtime.logger.error(error_msg)
        runtime.logger.error(traceback.format_exc())
        slack_client = runtime.new_slack_client()
        slack_client.bind_channel(f'openshift-{stream_version}')
        await slack_client.say(error_msg)
        raise

    except LockError as e:
        runtime.logger.error('Failed acquiring lock %s: %s', lock_name, e)
        raise

    finally:
        await lock_manager.destroy()


@cli.command("ocp4:mirror-rpms",
             help="Copy the plashet created earlier out to the openshift mirrors"
                  "This allows QE to easily find the RPMs we used in the creation of the images."
                  "These RPMs may be required for bare metal installs")
@click.option('--version', required=True, help='Full OCP version, e.g. 4.14-202304181947.p?')
@click.option('--assembly', required=True, help='Assembly name')
@click.option('--local-plashet-path', required=False, default='', help='Local path to built plashet')
@pass_runtime
@click_coroutine
async def mirror_rpms(runtime: Runtime, version: str, assembly: str, local_plashet_path: str):
    if assembly != 'stream':
        runtime.logger.info('No need to mirror rpms for non-stream assembly')
        return

    if not local_plashet_path:
        runtime.logger.info('No updated RPMs to mirror.')
        return

    stream_version = version.split('-')[0]  # e.g. 4.14 from 4.14-202304181947.p?
    s3_base_dir = f'/enterprise/enterprise-{stream_version}'

    # Create a Lock manager instance
    lock_policy = locks.LOCK_POLICY['mirroring_rpms']
    lock_manager = locks.new_lock_manager(
        internal_lock_timeout=lock_policy['lock_timeout'],
        retry_count=lock_policy['retry_count'],
        retry_delay_min=lock_policy['retry_delay_min']
    )
    lock_name = f'mirroring-rpms-lock-{stream_version}'

    # Sync plashets to mirror
    try:
        async with await lock_manager.lock(lock_name):
            s3_path = f'{s3_base_dir}/latest/'
            await sync_repo_to_s3_mirror(local_plashet_path, s3_path, runtime.dry_run)

            s3_path = f'/enterprise/all/{stream_version}/latest/'
            await sync_repo_to_s3_mirror(local_plashet_path, s3_path, runtime.dry_run)

        runtime.logger.info('Finished mirroring OCP %s to openshift mirrors', version)

    except ChildProcessError as e:
        error_msg = f'Failed syncing {local_plashet_path} repo to art-srv-enterprise S3: {e}',
        runtime.logger.error(error_msg)
        runtime.logger.error(traceback.format_exc())
        slack_client = runtime.new_slack_client()
        slack_client.bind_channel(f'openshift-{stream_version}')
        await slack_client.say(error_msg)
        raise

    except LockError as e:
        runtime.logger.error('Failed acquiring lock %s: %s', lock_name, e)
        raise

    finally:
        await lock_manager.destroy()
