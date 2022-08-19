import json
import os
import re
from collections import namedtuple
from pathlib import Path
from typing import Dict
from urllib.parse import quote, urljoin, urlparse

import click
from ghapi.all import GhApi
from pyartcd import exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.git import GitRepository
from pyartcd.runtime import Runtime
from ruamel.yaml import YAML

yaml = YAML(typ="rt")
yaml.default_flow_style = False
yaml.preserve_quotes = True


class ReviewCVPPipeline:
    def __init__(self, runtime: Runtime, group: str, assembly: str) -> None:
        self.runtime = runtime
        self.group = group
        self.assembly = assembly

        self._logger = runtime.logger
        self.working_dir = self.runtime.working_dir.absolute()
        self._slack_client = self.runtime.new_slack_client()

        # sets environment variables for Elliott and Doozer
        self._ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self.runtime.working_dir / "elliott-working")
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.runtime.working_dir / "doozer-working")
        if self._ocp_build_data_url:
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = self._ocp_build_data_url
            self._doozer_env_vars["DOOZER_DATA_PATH"] = self._ocp_build_data_url

    async def run(self):
        messages = []
        warnings = []

        # Get CVP test results
        cvp_report = await self._verify_cvp()

        # Write to cvp-test-results.yaml
        yaml.dump(cvp_report, self.working_dir / "cvp-test-results.yaml")

        # Parse sanity_tests results
        sanity_tests = cvp_report["sanity_tests"]
        passed, failed, missing = sanity_tests["passed"], sanity_tests["failed"], sanity_tests["missing"]
        messages.append(f"CVP sanity_tests - PASSED: {len(passed)}, FAILED: {len(failed)}, MISSING: {len(missing)}")
        self._logger.info(messages[-1])

        # Parse sanity_test_optional_checks results
        sanity_test_optional_checks = cvp_report.get("sanity_test_optional_checks")
        passed_optional, failed_optional, missing_optional = {}, {}, {}
        if sanity_test_optional_checks:
            passed_optional, failed_optional, missing_optional = sanity_test_optional_checks["passed"], sanity_test_optional_checks["failed"], sanity_test_optional_checks["missing"]
            messages.append(f"CVP sanity_test_optional_checks - PASSED: {len(passed_optional)}, FAILED: {len(failed_optional)}, MISSING: {len(missing_optional)}")
            self._logger.info(messages[-1])
            if failed_optional:
                # Clone ocp-build-data,
                # then create a PR to auto-fix common sanity_test_optional_checks failures.
                build_data_path = self.working_dir / "ocp-build-data-push"
                build_data = GitRepository(build_data_path, dry_run=self.runtime.dry_run)
                ocp_build_data_repo_push_url = self.runtime.config["build_config"]["ocp_build_data_repo_push_url"]
                await build_data.setup(ocp_build_data_repo_push_url)
                branch = f"auto-cvp-fix-{self.group}"
                await build_data.fetch_switch_branch(branch, self.group)
                warnings.extend(await self._resolve_content_set_failures(build_data_path, failed_optional))

                title = f"Automated CVP content_set_check fix for {self.group}"
                body = f"Created by build {self.runtime.get_job_run_url()}"
                pushed = await build_data.commit_push(f"{title}\n{body}")
                if pushed:
                    match = re.search(r"github\.com[:/](.+)/(.+)(?:.git)?", ocp_build_data_repo_push_url)
                    if not match:
                        raise ValueError(f"Couldn't create a pull request: {ocp_build_data_repo_push_url} is not a valid github repo")
                    pr_head = f"{match[1]}:{branch}"
                    result = await self._create_or_update_pull_request(owner="openshift", repo="ocp-build-data", base=self.group, head=pr_head, title=title, body=body)
                    pr_html_url = result.html_url
                    messages.append("")
                    messages.append(f"A PR has been created/updated to fix common CVP content_set_check failures: {pr_html_url}")
                    self._logger.info(messages[-1])

        if not failed and not failed_optional:
            self._logger.info("No CVP test failures")
            return

        if warnings:
            messages.append("")
            messages.append("Following are CVP test failures that can't be fixed by automation:")
            self._logger.info(messages[-1])
            for warning in warnings:
                messages.append(f"• {warning}")
                self._logger.info(messages[-1])

        messages.append("")
        messages.append(f"""Check <{self.runtime.get_job_run_url()}/consoleFull|build logs> and <{self.runtime.get_job_run_url()}/artifact/artcd_working/cvp-test-results.yaml/*view*/|cvp-test-results.yaml> for detailed CVP test results.""")
        self._logger.info(messages[-1])

        messages.append("""For more information about content_set_check, see https://docs.engineering.redhat.com/x/a05iEQ.
If you have any questions or encounter a CVP bug, drop a message to CVP gchat channel.""")
        self._logger.info(messages[-1])

        self._slack_client.bind_channel(self.group)
        slack_response = await self._slack_client.say(f"Review of CVP test results required for {self.group}. @release-artists")
        slack_thread = slack_response["message"]["ts"]
        await self._slack_client.say("\n".join(messages), thread_ts=slack_thread)

    async def _verify_cvp(self):
        cmd = [
            "elliott",
            f"--group={self.group}",
            f"--assembly={self.assembly}",
            "verify-cvp",
            "--all",
            "--include-content-set-check",
            "-o",
            "json"
        ]
        _, out, _ = await exectools.cmd_gather_async(cmd, env=self._elliott_env_vars, stderr=None)
        result = json.loads(out)
        return result

    def get_image_config(self, local_path: Path, dg_key: str):
        path = local_path / "images" / f"{dg_key}.yml"
        content = yaml.load(path)
        return content

    def save_image_config(self, local_path: Path, dg_key: str, content):
        path = local_path / "images" / f"{dg_key}.yml"
        yaml.dump(content, path)

    async def _create_or_update_pull_request(self, owner: str, repo: str, base: str, head: str, title: str, body: str):
        title = f"Automated CVP fix for {self.group}"
        body = f"Job run: {self.runtime.get_job_run_url()}"
        if self.runtime.dry_run:
            self._logger.warning("[DRY RUN] Would have created pull-request with head '%s', base '%s' title '%s', body '%s'", head, base, title, body)
            d = {"html_url": "https://github.example.com/foo/bar/pull/1234", "number": 1234}
            result = namedtuple('pull_request', d.keys())(*d.values())
            return
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required to create a pull request")
        api = GhApi(owner=owner, repo=repo, token=github_token)
        existing_prs = api.pulls.list(state="open", base=base, head=head)
        if not existing_prs.items:
            result = api.pulls.create(head=head, base=base, title=title, body=body, maintainer_can_modify=True)
        else:
            pull_number = existing_prs.items[0].number
            result = api.pulls.update(pull_number=pull_number, title=title, body=body)
        return result

    async def _resolve_content_set_failures(self, build_data_repo: Path, sanity_test_optional_checks: Dict):
        warnings = []
        for nvr, r in sanity_test_optional_checks.items():
            dg_key = r["dg_key"]
            image_config = self.get_image_config(build_data_repo, dg_key)

            def _update_repos(name, old, new):
                if new == old:
                    self._logger.info("[%s]%s unchanged", dg_key, name)
                    return
                self._logger.info("[%s]Updating %s from %s to %s...", dg_key, name, old, new)
                if new:
                    image_config[name] = sorted(new_enabled_repos)
                else:
                    del image_config[name]
            for check_name, check_result in r.get("diagnostic_report", {}).items():
                if check_name not in r["failed_checks"]:
                    continue
                for test_name, test_result in check_result.items():
                    symptom = test_result.get("symptom")
                    if not symptom:
                        continue
                    prescription = test_result.get("prescription")
                    if not prescription:
                        self._logger.warning("No prescription to treat %s: %s", nvr, symptom)
                        continue
                    for action in prescription:
                        action_name = action["action"]
                        if action_name == "remove_repos":
                            repos = action.get("value", [])
                            enabled_repos = set(image_config.get("enabled_repos", []))
                            new_enabled_repos = enabled_repos - set(repos)
                            _update_repos("enabled_repos", enabled_repos, new_enabled_repos)

                            non_shipping_repos = set(image_config.get("non_shipping_repos", []))
                            new_non_shipping_repos = non_shipping_repos - set(repos)
                            _update_repos("non_shipping_repos", non_shipping_repos, new_non_shipping_repos)
                        elif action_name == "add_non_shipping_repos":
                            repos = action.get("value", [])
                            enabled_repos = set(image_config.get("enabled_repos", []))
                            new_enabled_repos = enabled_repos | set(repos)
                            _update_repos("enabled_repos", enabled_repos, new_enabled_repos)

                            non_shipping_repos = set(image_config.get("non_shipping_repos", []))
                            new_non_shipping_repos = non_shipping_repos | set(repos)
                            _update_repos("non_shipping_repos", non_shipping_repos, new_non_shipping_repos)
                        elif action_name == "add_repos":
                            repos = action.get("value", [])
                            enabled_repos = set(image_config.get("enabled_repos", []))
                            new_enabled_repos = enabled_repos | set(repos)
                            _update_repos("enabled_repos", enabled_repos, new_enabled_repos)

                            non_shipping_repos = set(image_config.get("non_shipping_repos", []))
                            new_non_shipping_repos = non_shipping_repos - set(repos)
                            _update_repos("non_shipping_repos", non_shipping_repos, new_non_shipping_repos)
                        elif action_name == "see_parent_builds":
                            builds = action.get("value", [])
                            for b in builds:
                                build_url = f"https://brewweb.devel.redhat.com/buildinfo?buildID={b['id']}"
                                self._logger.warning("[%s]See CVP test result for parent build %s (dg_key: %s): %s ", dg_key, b["nvr"], b.get("dg_key", "?"), build_url)
                        elif action_name == "warn":
                            detail = action.get("value", {})
                            warning = f'*{dg_key}* {action.get("note")}: {detail}'
                            warnings.append(warning)
                            self._logger.warning(warning)
                        else:
                            self._logger.warning("[%s]Unhandled action: %s - %s", dg_key, action_name, action)
            self.save_image_config(build_data_repo, dg_key, image_config)
            self._logger.info(f"Fixed {test_name} for {dg_key}")
        return warnings


@cli.command("review-cvp")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly. e.g. 4.9.1")
@pass_runtime
@click_coroutine
async def reivew_cvp(runtime: Runtime, group: str, assembly: str):
    pipeline = ReviewCVPPipeline(runtime, group, assembly)
    await pipeline.run()
