import os
import shutil

from pyartcd.exectools import cmd_assert_async


async def clone(git_repo: str, git_ref: str, directory: os.PathLike = None):
    directory = str(directory) if directory else "."
    shutil.rmtree(directory, ignore_errors=True)
    cmds = [
        ["git", "init", directory],
        ["git", "-C", directory, "remote", "add", "origin", git_repo],
        ["git", "-C", directory, "fetch", "--depth=1", "origin", git_ref],
        ["git", "-C", directory, "checkout", "FETCH_HEAD"],
        ["git", "-C", directory, "submodule", "update", "--init"],
    ]
    env = os.environ.copy()
    for cmd in cmds:
        await cmd_assert_async(cmd, env=env)
