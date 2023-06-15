import os
from pyartcd import exectools
from tenacity import retry, stop_after_attempt, wait_fixed


async def sync_repo_to_s3_mirror(local_dir: str, s3_path: str, dry_run: bool = False, remove_old: bool = True):
    # Sync is not transactional. If we update repomd.xml before files it references are populated,
    # users of the repo will get a 404. So we run in three passes:
    # 1. On the first pass, exclude files like repomd.xml and do not delete any old files.
    #    This ensures that we  are only adding new rpms, filelist archives, etc.
    await sync_dir_to_s3_mirror(local_dir, s3_path, exclude='*/repomd.xml', include_only='', dry_run=dry_run, remove_old=False)
    # 2. On the second pass, include only the repomd.xml.
    await sync_dir_to_s3_mirror(local_dir, s3_path, exclude='', include_only='*/repomd.xml', dry_run=dry_run, remove_old=False)

    # For most repos, clean up the old rpms so they don't grow unbounded. Specify remove_old=false to prevent this step.
    # Otherwise:
    # 3. Everything should be synced in a consistent way -- delete anything old with --delete.
    if remove_old:
        await sync_dir_to_s3_mirror(local_dir, s3_path, exclude='', include_only='', dry_run=dry_run, remove_old=True)


async def sync_dir_to_s3_mirror(local_dir: str, s3_path: str, exclude: str, include_only: str,
                                dry_run: bool = False, remove_old: bool = True):
    """
    Sync a directory to an s3 bucket.

    :param local_dir: The directory to sync.
    :param s3_path: The s3 path to sync to.
    :param exclude: A regex to exclude certain files.
    :param include_only: A regex to only sync certain files.
    :param dry_run: Print what would happen, but don't actually do it.
    :param remove_old: Remove old files with --delete
    """
    if not s3_path.startswith('/') or \
            s3_path.startswith('/pub/openshift-v4/clients') or \
            s3_path.startswith('/pub/openshift-v4/amd64') or \
            s3_path.startswith('/pub/openshift-v4/arm64') or \
            s3_path.startswith('/pub/openshift-v4/dependencies'):
        raise Exception(
            f'Invalid location on s3 ({s3_path}); these are virtual/read-only locations on the s3 '
            'backed mirror. Qualify your path with /pub/openshift-v4/<brew_arch_name>/ instead.')

    env = os.environ.copy()
    full_s3_path = f's3://art-srv-enterprise{s3_path}'  # Note that s3_path has / prefix.
    base_cmd = ['aws', 's3', 'sync', '--no-progress', '--exact-timestamps']
    if dry_run:
        base_cmd.append('--dryrun')
    if exclude:
        base_cmd += ['--exclude', exclude]
    elif include_only:  # include_only will over-ride exclude.
        base_cmd += ['--exclude', '*', '--include', include_only]
    if remove_old:
        base_cmd.append('--delete')
    base_cmd += [local_dir, full_s3_path]
    await retry(
        wait=wait_fixed(30),  # wait for 30 seconds between retries
        stop=(stop_after_attempt(3)),  # max 3 attempts
        reraise=True
    )(exectools.cmd_assert_async)(base_cmd, env=env)
