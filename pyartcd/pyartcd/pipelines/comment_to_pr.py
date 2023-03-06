import asyncio
import pprint
import sys
import re
import aiohttp
import requests
import logging
import os
import click
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime
from typing import Optional
from ruamel.yaml import YAML
from ghapi.all import GhApi  # https://ghapi.fast.ai/ "provides 100% always-updated coverage of the entire GitHub API."
from string import Template

yaml = YAML(typ="rt")
yaml.preserve_quotes = True

# https://github.com/openshift-eng/art-dashboard-server/tree/master/api/README.md
ART_DASH_API_ENDPOINT = "http://art-dash-server-aos-art-web.apps.ocp4.prod.psi.redhat.com/api/v1"
GITHUB_API_URL_REPOS = "https://api.github.com/repos"
GITHUB_TOKEN = os.environ.get("OPENSHIFT_BOT_TOKEN")
HEADER = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# Message to be posted to the comment
BUILD_STATUS_COMMENT = Template(f"**[ART PR BUILD NOTIFIER]** _(beta)_\n\n"
                                f"This PR has been included in build "
                                f"[$nvr](https://brewweb.engineering.redhat.com/brew/buildinfo?buildID=$build_id) "
                                f"for distgit *$distgit_name*. \n All builds following this will include this PR.")


class GithubRepo:
    def __init__(self, github_org: str, github_repo: str, openshift_version: str, logger: logging.Logger):
        self._org = github_org
        self._repo = github_repo
        self._openshift_version = openshift_version
        self._prs = []
        self._github_api = GhApi(owner=self._org, repo=self._repo, token=GITHUB_TOKEN)
        self._logger = logger

    def set_prs(self, prs):
        self._prs = prs

    def get_prs(self):
        return self._prs

    def get_pr_from_merge_commit(self, sha: str):
        """
        Get the PR url and number from the merge commit
        """
        # https://docs.github.com/en/rest/commits/commits#list-pull-requests-associated-with-a-commit
        pulls = self._github_api.repos.list_pull_requests_associated_with_commit(sha)

        if len(pulls) == 1:
            pull_url = pulls[0]["html_url"]
            pr_no = pulls[0]["number"]

            self._logger.info(f"PR from merge commit {sha}: {pull_url}")
            return pull_url, pr_no

    def _get_branch_ref(self) -> str:
        """
        Return the SHA of release-{MAJOR}.{MINOR} HEAD
        """
        # https://docs.github.com/en/rest/branches/branches#get-a-branch
        sha = self._github_api.repos.get_branch(f"release-{self._openshift_version}")["commit"]["sha"]
        self._logger.info(f"Branch ref of release-{self._openshift_version}: {sha}")
        return sha

    def _get_commit_time(self, build_commit_github_sha) -> str:
        """
        Return the timestamp associated with a commit: e.g. "2022-10-21T19:48:29Z"
        """
        # https://docs.github.com/en/rest/commits/commits#get-a-commit
        timestamp = self._github_api.repos.get_commit(build_commit_github_sha)["commit"]["committer"]["date"]
        self._logger.info(f"Timestamp of commit {build_commit_github_sha}: {timestamp}")
        return timestamp

    def _get_commits_after(self, sha) -> list:
        """
        Return commits in a repo from the given time (includes the current commit) of from release branch.
        """
        branch_ref = self._get_branch_ref()
        datetime = self._get_commit_time(sha)

        # https://docs.github.com/en/rest/commits/commits#list-commits
        commits = self._github_api.repos.list_commits(sha=branch_ref, since=datetime)

        result = []
        for data in commits:
            result.append(data["sha"])

        self._logger.info(f"Commits after large successful build: {result}")
        return result

    def _get_comments_from_pr(self, pr_no: int):
        """
        Get the comments from a given pull request
        """
        # https://docs.github.com/en/rest/issues/comments#list-issue-comments
        # PR is considered an issue in the context of GitHub API, so PR number is issue number.
        # Add pr number to the url to get the comments from that particular PR.
        comments = self._github_api.issues.list_comments(pr_no)
        self._logger.debug(f"Comments from PR {pr_no}: {comments}")
        return comments

    def check_if_pr_needs_reporting(self, pr_no: int, type_: str):
        """
        Check the comments to see if the bot has already reported so as not to prevent spamming

        repo_name: Name of the repository. Eg: console
        pr_no: The Pull request ID/No
        type_: The type of notification. PR | NIGHTLY | RELEASE
        """
        comments = self._get_comments_from_pr(pr_no)

        for comment in comments:
            body = comment["body"]

            if f"[ART PR {type_} NOTIFIER]" in body:
                self._logger.warning(f"A {type_} comment already exists in the PR")
                return False
        return True


class Distgit(GithubRepo):
    def __init__(self, distgit_name: str, nvr: str, github_org: str, github_repo: str, build_id: int,
                 openshift_version: str, logger: logging.Logger):
        super().__init__(github_org=github_org, github_repo=github_repo, logger=logger,
                         openshift_version=openshift_version)
        self._distgit_name = distgit_name
        self._nvr = nvr
        self._build_id = build_id

    def post_to_pull_request(self, pr_no: int, pr_url: str) -> None:
        """
        Post to a PR with the given message
        """
        # https://docs.github.com/en/rest/issues/comments#list-issue-comments
        # PR is considered an issue in the context of GitHub API, so PR number is issue number.
        # Add pr number to the url to get the comments from that particular PR.
        self._github_api.issues.create_comment(pr_no,
                                               BUILD_STATUS_COMMENT.substitute(nvr=self._nvr, build_id=self._build_id,
                                                                               distgit_name=self._distgit_name))
        self._logger.info(f"Commented on PR: {pr_url}")

    async def get_previous_distgit_commit(self, dg_name, dg_commit):
        """
        Get the distgit commit of the previous successful build of that distgit name.
        """
        url = f"{ART_DASH_API_ENDPOINT}/builds?dg_name={dg_name}&brew_task_state=success&" \
              f"group=openshift-{self._openshift_version}"
        self._logger.info(f"Querying art-dash with: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                response = await resp.json()

        if response["count"] > 0:
            results = response["results"]
            for index, response in enumerate(results):
                if response["dg_commit"] == dg_commit:
                    return results[index + 1]["dg_commit"]

    async def get_github_commit_from_dg_commit(self, dg_commit):
        """
        Find the GitHub commit from the distgit commit using the API server.
        """
        url = f"{ART_DASH_API_ENDPOINT}/builds?dg_commit={dg_commit}&brew_task_state=success&" \
              f"group=openshift-{self._openshift_version}"
        self._logger.info(f"Querying art-dash with: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                response = await resp.json()

        if response["count"] == 1:
            return response["results"][0]["label_io_openshift_build_commit_id"]
        else:
            self._logger.error("More than one distgit commits found")
            sys.exit(1)

    def get_commits_between(self, latest, previous):
        """
        Get the commits between two commits (does not include the 'previous' commit).
        Sometimes the previous build has the same GitHub commit, but different distgit commit.
        The logic in function _check_if_pr_needs_reporting will check to see if there's already a comment in
        the same PR.
        """
        commits_after = self._get_commits_after(previous)
        latest_commit_index = commits_after.index(latest)

        # Exclude the last commit, since it was already built
        between_commits = commits_after[latest_commit_index:len(commits_after) - 1]

        return between_commits


class CommentOnPrPipeline:
    """
    Comment on origin PR.
    """

    def __init__(self, runtime: Runtime, job_name: str, job_id: str, openshift_version: str,
                 logger: Optional[logging.Logger] = None):
        self.runtime = runtime
        self.job_name = job_name
        self.job_id = job_id
        self.openshift_version = openshift_version
        self._logger = logger or runtime.logger

    async def _get_distgit(self, build):
        # extract data from the API result
        build_commit_url = build["label_io_openshift_build_source_location"]

        # Extract org name, repo name and commit sha
        regex = r"^https:\/\/github\.com\/(?P<org>[a-z-]+)\/(?P<repo_name>[a-z-]+)$"
        match = re.match(regex, build_commit_url)
        self._logger.debug(f"regex matches: {pprint.pformat(match.groupdict())}")
        org, repo_name = match.groupdict().values()

        distgit = Distgit(distgit_name=build["dg_name"], nvr=build["build_0_nvr"], github_org=org,
                          github_repo=repo_name, build_id=build["build_0_id"],
                          openshift_version=self.openshift_version, logger=self._logger)
        self._logger.info(f"Distgit: {vars(distgit)}")

        # Get the current and previous distgit commit that was built successfully
        dg_commit = build["dg_commit"]
        previous_dg_commit = await distgit.get_previous_distgit_commit(build["dg_name"], dg_commit)

        # Get the current and previous built GitHub commit that was built successfully
        latest_github_commit = await distgit.get_github_commit_from_dg_commit(dg_commit)
        previous_github_commit = await distgit.get_github_commit_from_dg_commit(previous_dg_commit)

        self._logger.info(f"Latest commit distgit:github  :: {dg_commit} : {latest_github_commit}")
        self._logger.info(f"Previous commit distgit:github  :: {previous_dg_commit} : {previous_github_commit}")

        # Multiple PRs might have been merged between current and previous successful build.
        commits_between_builds = distgit.get_commits_between(latest_github_commit, previous_github_commit)
        self._logger.info(f"Commits between those two: {pprint.pformat(commits_between_builds)}")

        prs = []
        for commit_sha in commits_between_builds:
            # Find the PR from the merge commit
            pull_url, pr_no = distgit.get_pr_from_merge_commit(sha=commit_sha)

            if (pull_url, pr_no) not in prs and distgit.check_if_pr_needs_reporting(pr_no, "BUILD"):
                # Sometimes, due to force push, more than one commit may show up in commit history of the
                # release branch, but will belong to the same PR. If that's the case, we don't need to post to
                # the PR more than once. Hence, checking (pull_url, pr_no) not in prs
                # Also check if the bot had already commented on the PR that we are looking at
                prs.append((pull_url, pr_no))

        self._logger.info(f"PRs that need to be posted to {pprint.pformat(prs)}")
        distgit.set_prs(prs)

        return distgit

    def _builds_from_job(self):
        """
        Find the distgits that has PRs that needs reporting to.
        """
        url = f"{ART_DASH_API_ENDPOINT}/builds?jenkins_build_url__icontains={self.job_name}/{self.job_id}"
        self._logger.info(f"Querying ART Dash server with url: {url}")

        response = requests.get(url)
        if response.status_code != 200:
            self._logger.error(f"ART DASH Server error. Status code: {response.status_code}")
            sys.exit(1)

        data = response.json()
        self._logger.debug(f"Response: {pprint.pformat(data)}")

        if data["count"] > 0:
            api_results = data["results"]

            tasks = []
            for build in api_results:
                if build["brew_task_state"] != "success":
                    # Do not check for unsuccessful builds
                    self._logger.info(f"Skipping Build {build['build_0_id']} because it failed.")
                    continue

                tasks.append(asyncio.ensure_future(self._get_distgit(build)))

            distgits = asyncio.gather(*tasks)

            return distgits
        else:
            self._logger.error(f"No builds were found for job no: {self.job_id}")

    async def _check_builds(self):
        """
        Returns a list of repo PRs that needs reporting to based on successful builds.
        """
        distgits = await self._builds_from_job()
        for distgit in distgits:
            # Log the object to see if the data is populated correctly
            # https://docs.python.org/2/library/functions.html#vars
            self._logger.info(pprint.pformat(vars(distgit)))

            for pr_url, pr_no in distgit.get_prs():
                distgit.post_to_pull_request(pr_no=pr_no, pr_url=pr_url)

    def _check_nightlies(self):
        pass

    def _check_releases(self):
        pass

    async def run(self):
        await self._check_builds()


@cli.command("comment-status-to-pr")
@click.option("--job-base-name", metavar="JOB_BASE_NAME", default=None,
              help="Base name of the parent job. Eg: build/ocp4")
@click.option("--job-build-number", metavar="JOB_BUILD_NUMBER", default=None, help="Build number of the parent job")
@click.option("--openshift-version", metavar="OPENSHIFT_VERSION", default=None, help="Openshift version, eg: 4.12")
@pass_runtime
@click_coroutine
async def comment_status_to_pr(runtime: Runtime, job_base_name: str, job_build_number: str, openshift_version: str):
    # Replace encoded forward slashes with the actual one, if present
    job_base_name = job_base_name.replace("%2F", "/")

    # Get the name of the parent job. Eg: ocp4
    _, job_name = job_base_name.split("/")

    pipeline = CommentOnPrPipeline(runtime=runtime, job_name=job_name, job_id=job_build_number,
                                   openshift_version=openshift_version)
    await pipeline.run()
