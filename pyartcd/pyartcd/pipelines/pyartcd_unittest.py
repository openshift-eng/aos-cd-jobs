from io import StringIO
import logging
import os
import re
from asyncio.subprocess import STDOUT
from typing import Optional
from urllib.parse import urlparse

import click
from pyartcd import exectools, git
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.github import GitHubAPI
from pyartcd.runtime import Runtime


class PyartcdUnittestPipeline:
    def __init__(self, runtime: Runtime, git_repo: str, git_ref: str, comment: bool,
                 github_repo: Optional[str], github_pr: Optional[int]) -> None:
        self.runtime = runtime
        self.git_repo = git_repo
        self.git_ref = git_ref
        self.comment = comment
        if not github_repo:
            git_repo_parsed = urlparse(git_repo)
            if git_repo_parsed.hostname == "github.com":
                github_repo = git_repo_parsed.path.strip('/')
        self.github_repo = github_repo
        if not github_pr:
            pattern = re.compile(r"pull/(\d+)/head")
            match = pattern.findall(git_ref)
            if match:
                github_pr = int(match[0])
        if self.github_repo and self.github_repo.endswith(".git"):
            self.github_repo = self.github_repo[:-4]
        self.github_pr = github_pr
        self.logger = logging.getLogger(__name__)

    async def run(self):
        env = os.environ.copy()
        path = self.runtime.working_dir.joinpath("aos-cd-jobs")

        if path.exists():
            self.logger.warning("Directory %s already exists. Skip git clone.", path.absolute())
        else:
            await git.clone(self.git_repo, self.git_ref, str(path))
        cmds = [
            ["flake8"],
            ["coverage", "run", "--branch", "--source", "pyartcd", "-m", "unittest", "discover", "-t", ".", "-s", "tests/"],
            ["coverage", "report"],
        ]

        result = ""
        rc = 0

        for cmd in cmds:
            result += f"Test {cmd}:\n"
            self.logger.info(f"Running {cmd}...")
            rc, out, _ = await exectools.cmd_gather_async(cmd, env=env, cwd=path / "pyartcd", check=False, stderr=STDOUT)
            result += out + "\n"
            if rc != 0:
                break

        if rc == 0:
            msg = f"Test result is SUCCESS:\n```\n{result}\n```"
        else:
            msg = f"Test result is FAILURE:\n```\n{result}\n```"
        self.logger.info(msg)

        if self.comment:
            github = GitHubAPI()
            if not self.runtime.dry_run:
                await github.add_comment(msg, self.github_repo, self.github_pr)
            else:
                self.logger.info("Would have added a comment to PR %s %s: %s", self.github_repo, self.github_pr, msg)

        if rc != 0:
            raise ValueError("Error running unit tests. Check logs for more info.")


@cli.command("pyartcd-unittest")
@click.option("--git-repo", metavar="URL",
              help="Git repository URL.")
@click.option("--git-ref", metavar="REF",
              help="Git commit hash, branch, or tag to test against.")
@click.option("--comment", is_flag=True,
              help="If specified, make a comment on the specified GitHub PR.")
@click.option("--github-repo", metavar="NAME",
              help="The GitHub repo for making a comment on PR.")
@click.option("--github-pr", metavar="NUM", type=int,
              help="The PR number for making a comment.")
@pass_runtime
@click_coroutine
async def pyartcd_unittest(runtime: Runtime, git_repo: str, git_ref: str, comment: bool,
                           github_repo: Optional[str], github_pr: Optional[int]):
    pipeline = PyartcdUnittestPipeline(runtime, git_repo, git_ref, comment, github_repo, github_pr)
    await pipeline.run()
