# pyartcd Git helpers

from logging import getLogger
from pathlib import Path
import subprocess
from os import PathLike
import os
import shutil
import pygit2

from pyartcd import StrOrBytesPath, exectools

LOGGER = getLogger(__name__)

class GitRepository:
    def __init__(self, directory: StrOrBytesPath, dry_run: bool = False) -> None:
        self._directory = Path(directory)
        self._dry_run = dry_run

    async def setup(self, remote_url, upstream_remote_url=None):
        """ Initialize a git repository with specified remote URL and an optional upstream remote URL.
        """
        # Ensure local repo directory exists
        self._directory.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        repo_dir = str(self._directory)
        await exectools.cmd_assert_async(["git", "init", "--", repo_dir], env=env)

        # Add remotes
        _, out, _ = await exectools.cmd_gather_async(["git", "-C", repo_dir, "remote"], env=env)
        remotes = set(out.strip().split())
        if "origin" not in remotes:
            await exectools.cmd_assert_async(["git", "-C", repo_dir, "remote", "add", "--", "origin", remote_url], env=env)
        else:
            await exectools.cmd_assert_async(["git", "-C", repo_dir, "remote", "set-url", "--", "origin", remote_url], env=env)
        if upstream_remote_url:
            if 'upstream' not in remotes:
                await exectools.cmd_assert_async(["git", "-C", repo_dir, "remote", "add", "--", "upstream", upstream_remote_url], env=env)
            else:
                await exectools.cmd_assert_async(["git", "-C", repo_dir, "remote", "set-url", "--", "upstream", upstream_remote_url], env=env)
        elif 'upstream' in remotes:
            await exectools.cmd_assert_async(["git", "-C", repo_dir, "remote", "remove", "upstream"], env=env)

    async def fetch_switch_branch(self, branch, upstream_ref=None):
        """ Fetch `upstream_ref` from the remote repo, create the `branch` and start it at `upstream_ref`.
        If `branch` already exists, then reset it to `upstream_ref`.
        """
        env = os.environ.copy()
        repo_dir = str(self._directory)
        # Fetch remote
        _, out, _ = await exectools.cmd_gather_async(["git", "-C", repo_dir, "remote"], env=env)
        remotes = set(out.strip().split())
        fetch_remote = "upstream" if "upstream" in remotes else "origin"
        await exectools.cmd_assert_async(["git", "-C", repo_dir, "fetch", "--depth=1", "--", fetch_remote, upstream_ref or branch], env=env)

        # Check out FETCH_HEAD
        await exectools.cmd_assert_async(["git", "-C", repo_dir, "checkout", "-f", "FETCH_HEAD"], env=env)
        await exectools.cmd_assert_async(["git", "-C", repo_dir, "checkout", "-B", branch], env=env)
        await exectools.cmd_assert_async(["git", "-C", repo_dir, "submodule", "update", "--init"], env=env)

        # Clean workdir
        await exectools.cmd_assert_async(["git", "-C", repo_dir, "clean", "-fdx"], env=env)

    async def commit_push(self, commit_message: str):
        """ Create a commit that includes all file changes in the working tree and push the commit to the remote repository.
        If there are no changes in thw working tree, do nothing.
        """
        env = os.environ.copy()
        repo_dir = str(self._directory)
        cmd = ["git", "-C", repo_dir, "add", "."]
        await exectools.cmd_assert_async(cmd, env=env)
        cmd = ["git", "-C", repo_dir, "status", "--porcelain", "--untracked-files=no"]
        _, out, _ = await exectools.cmd_gather_async(cmd, env=env)
        if not out.strip():  # Nothing to commit
            return False
        cmd = ["git", "-C", repo_dir, "commit", "--message", commit_message]
        await exectools.cmd_assert_async(cmd, env=env)
        cmd = ["git", "-C", repo_dir, "push", "-f", "origin", "HEAD"]
        if not self._dry_run:
            await exectools.cmd_assert_async(cmd, env=env)
        else:
            LOGGER.warning("[DRY RUN] Would have run %s", cmd)
        return True
