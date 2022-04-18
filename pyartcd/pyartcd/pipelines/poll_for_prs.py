
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import click
from pyartcd import exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


class PollForPRsPipeline:
    def __init__(self, git_repo: str, working_dir: os.PathLike = ".", logger=None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.git_repo = git_repo
        self.working_dir = Path(working_dir)

    async def run(self):
        repo_url = urlparse(self.git_repo)
        canonical_repo_url = urlunparse(repo_url)
        state_store_dir = self.working_dir / "state_store"
        state_store_dir.mkdir(parents=True, exist_ok=True)
        state_file_name = f"{repo_url.scheme}__{repo_url.netloc}__{repo_url.path.replace('/', '_')}.json"
        state_file_path = state_store_dir / state_file_name
        new_state_file_name = state_file_name + ".tmp"
        new_state_file_path = state_store_dir / new_state_file_name
        old_state = {}
        if state_file_path.exists():
            with state_file_path.open("r") as f:
                old_state = json.load(f)
        new_state = {}

        cmd = ["git", "ls-remote", "--", canonical_repo_url, "refs/pull/*/head"]
        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None)
        for line in out.splitlines():
            commit_hash, ref = line.split("\t")
            new_state[ref] = commit_hash

        changed_refs = {}

        for ref, new_commit_hash in new_state.items():
            old_commit_hash = old_state.get(ref)
            if commit_hash and new_commit_hash != old_commit_hash:
                changed_refs[ref] = {"old": old_commit_hash, "new": new_commit_hash}
                self.logger.info("PR change Detected: %s (%s -> %s)", ref, old_commit_hash, new_commit_hash)

        if changed_refs:
            self.logger.info("Saving current state...")
            # write to a temp file then rename it to avoid content curruption
            with new_state_file_path.open("w") as f:
                json.dump(new_state, f)
            new_state_file_path.rename(state_file_path)
            self.logger.info("Saved")
        else:
            self.logger.info("No changes.")

        # dump the result to stdout
        json.dump(changed_refs, sys.stdout)


@cli.command("poll-for-prs")
@click.option("--git-repo", metavar="URL",
              help="Git repository URL.")
@pass_runtime
@click_coroutine
async def poll_for_prs(runtime: Runtime, git_repo: str):
    pipeline = PollForPRsPipeline(git_repo, runtime.working_dir, logger=runtime.logger)
    await pipeline.run()


async def main():
    git_repo = "https://github.com/openshift/aos-cd-jobs.git"
    pipeline = PollForPRsPipeline(git_repo)
    await pipeline.run()

if __name__ == "__main__":
    asyncio.run(main())
