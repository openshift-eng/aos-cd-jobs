import os
import traceback

import click
from aioredlock import LockError

from pyartcd import exectools, locks
from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd.runtime import Runtime


async def sync_repo_to_s3_mirror(local_dir: str, s3_path: str, dry_run: bool):
    if not s3_path.startswith('/') or \
            s3_path.startswith('/pub/openshift-v4/clients') or \
            s3_path.startswith('/pub/openshift-v4/amd64') or \
            s3_path.startswith('/pub/openshift-v4/arm64') or \
            s3_path.startswith('/pub/openshift-v4/dependencies'):
        raise Exception(
            f'Invalid location on s3 ({s3_path}); these are virtual/read-only locations on the s3 '
            'backed mirror. Qualify your path with /pub/openshift-v4/<brew_arch_name>/ instead.')

    # Sync is not transactional. If we update repomd.xml before files it references are populated,
    # users of the repo will get a 404. So we run in three passes:
    # 1. On the first pass, exclude files like repomd.xml and do not delete any old files.
    #    This ensures that we  are only adding new rpms, filelist archives, etc.
    # 2. On the second pass, include only the repomd.xml.
    base_cmd = ['aws', 's3', 'sync', '--no-progress', '--exact-timestamps']
    if dry_run:
        base_cmd.append('--dryrun')

    cmd = base_cmd + [
        '--exclude', '*/repomd.xml', local_dir,
        f's3://art-srv-enterprise{s3_path}'  # Note that s3_path has / prefix.
    ]
    env = os.environ.copy()
    await exectools.cmd_assert_async(cmd, env=env)

    cmd = base_cmd + [
        '--exclude', '*', '--include', '*/repomd.xml', local_dir,
        f's3://art-srv-enterprise{s3_path}'
    ]
    await exectools.cmd_assert_async(cmd, env=env)


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
    retry_policy = locks.RETRY_POLICY['mirroring_rpms']
    lock_manager = locks.new_lock_manager(
        internal_lock_timeout=locks.LOCK_TIMEOUTS['olm-bundle'],
        retry_count=retry_policy['retry_count'],
        retry_delay_min=retry_policy['retry_delay_min']
    )
    lock_name = f'mirroring-rpms-lock-{stream_version}'

    # Sync plashets to mirror
    try:
        async with await lock_manager.lock(lock_name):
            s3_path = f'{s3_base_dir}/latest/'
            await sync_repo_to_s3_mirror(local_plashet_path, s3_path, runtime.dry_run)

            s3_path = f'/enterprise/all/{stream_version}/latest/'
            await sync_repo_to_s3_mirror(local_plashet_path, s3_path, runtime.dry_run)

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

    runtime.logger.info('Finished mirroring OCP %s to openshift mirrors', version)
