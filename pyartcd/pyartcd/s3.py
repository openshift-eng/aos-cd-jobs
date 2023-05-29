import os

from pyartcd import exectools


async def sync_repo_to_s3_mirror(local_dir: str, s3_path: str, dry_run: bool = False, remove_old: bool = True):
    if not s3_path.startswith('/') or \
            s3_path.startswith('/pub/openshift-v4/clients') or \
            s3_path.startswith('/pub/openshift-v4/amd64') or \
            s3_path.startswith('/pub/openshift-v4/arm64') or \
            s3_path.startswith('/pub/openshift-v4/dependencies'):
        raise Exception(
            f'Invalid location on s3 ({s3_path}); these are virtual/read-only locations on the s3 '
            'backed mirror. Qualify your path with /pub/openshift-v4/<brew_arch_name>/ instead.')

    full_s3_path = f's3://art-srv-enterprise{s3_path}'  # Note that s3_path has / prefix.

    # Sync is not transactional. If we update repomd.xml before files it references are populated,
    # users of the repo will get a 404. So we run in three passes:
    # 1. On the first pass, exclude files like repomd.xml and do not delete any old files.
    #    This ensures that we  are only adding new rpms, filelist archives, etc.
    # 2. On the second pass, include only the repomd.xml.
    base_cmd = ['aws', 's3', 'sync', '--no-progress', '--exact-timestamps']
    if dry_run:
        base_cmd.append('--dryrun')

    cmd = base_cmd + [
        '--exclude', '*/repomd.xml', local_dir, full_s3_path
    ]
    env = os.environ.copy()
    await exectools.cmd_assert_async(cmd, env=env)

    cmd = base_cmd + [
        '--exclude', '*', '--include', '*/repomd.xml', local_dir, full_s3_path
    ]

    # aws s3 sync has been observed to hang before: retry for max 3 times
    await exectools.retry_async(cmd, max_retries=3, env=env)

    # For most repos, clean up the old rpms so they don't grow unbounded. Specify remove_old=false to prevent this step.
    # Otherwise:
    # 3. Everything should be synced in a consistent way -- delete anything old with --delete.
    if remove_old:
        cmd = base_cmd + [
            '--delete', local_dir, full_s3_path
        ]

        # aws s3 sync has been observed to hang before: retry for max 3 times
        await exectools.retry_async(cmd, max_retries=3, env=env)
