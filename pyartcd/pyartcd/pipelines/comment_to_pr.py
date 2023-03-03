import pprint
import sys

import requests
import logging
import os
import click
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime
from pyartcd import exectools
from typing import Optional
from ruamel.yaml import YAML

yaml = YAML(typ="rt")
yaml.preserve_quotes = True

GITHUB_API_URL_REPOS = "https://api.github.com/repos"


class CommentOnPrPipeline:
    """
    Comment on origin PR about the status of builds.
    """

    def __init__(self, runtime: Runtime, job: str, logger: Optional[logging.Logger] = None):
        self.runtime = runtime
        self.job = job
        self._logger = logger or runtime.logger
        self._working_dir = self.runtime.working_dir.absolute()

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._working_dir / "doozer-working")

    def _post_to_pull_request(self, org: str, repo: str, pr_no: int, message: str, pr_url: str) -> None:
        github_url = f"{GITHUB_API_URL_REPOS}/{org}/{repo}/issues/{pr_no}/comments"
        github_token = os.environ.get("OPENSHIFT_BOT_TOKEN")
        header = {"Authorization": f"Bearer {github_token}"}
        data = {"body": message}

        github_response = requests.post(github_url, headers=header, json=data)
        if github_response.status_code != 201:
            self._logger.error(pprint.pformat(github_response.json()))
            sys.exit(1)
        self._logger.debug(f"Status code: {github_response.status_code}")
        self._logger.debug(f"Response: {pprint.pformat(github_response.json())}")
        self._logger.info(f"Commented on PR: {pr_url}")

    async def run(self):
        cmd = [
            "doozer",
            "comment-on-pr:from-job",
            "--job", self.job
        ]
        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=self._doozer_env_vars)

        if out:
            self._logger.info(out)
            pull_requests = yaml.load(out)["from_builds"]

            if not pull_requests:
                self._logger.info("PRs already include the comments")
                return

            for pr in pull_requests:
                org, repo_name, pr_no, build_id, distgit_name, nvr, pr_url = pr["org"], pr["repo_name"], pr["pr_no"], \
                    pr["build_id"], pr["distgit_name"], pr["nvr"], pr["pr_url"]

                message = f"**[ART PR BUILD NOTIFIER]** _(beta)_\n\n" \
                          f"This PR has been included in build " \
                          f"[{nvr}](https://brewweb.engineering.redhat.com/brew/buildinfo?buildID={build_id}) " \
                          f"for distgit _{distgit_name}_. \n All builds following this will include this PR."

                self._post_to_pull_request(org, repo_name, pr_no, message, pr_url)


@cli.command("comment-status-to-pr")
@click.option("--job-base-name", metavar="JOB_BASE_NAME", default=None,
              help="Base name of the parent job. Eg: build/ocp4")
@click.option("--job-build-number", metavar="JOB_BUILD_NUMBER", default=None, help="Build number of the parent job")
@pass_runtime
@click_coroutine
async def comment_status_to_pr(runtime: Runtime, job_base_name: str, job_build_number: str):
    """
    Finds the PRs from which a job was fired (like ocp4) and then comments on them about the build details.

    job_base_name: The parent job name eg: build/ocp4
    job_build_number: The build number of the parent job
    """
    # Replace encoded forward slashes with the actual one, if present
    job_base_name = job_base_name.replace("%2F", "/")

    # Get the name of the parent job. Eg: ocp4
    _, job = job_base_name.split("/")

    parent_job = f"{job}/{job_build_number}"

    pipeline = CommentOnPrPipeline(runtime=runtime, job=parent_job)
    await pipeline.run()
