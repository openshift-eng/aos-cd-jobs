import json
import logging
import os
import re
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from subprocess import PIPE, CalledProcessError
from typing import Dict, List, Optional, Tuple

import aiofiles
import click
import jinja2
from elliottlib.assembly import assembly_group_config
from elliottlib.errata import get_bug_ids
from elliottlib.model import Model
from jira.resources import Issue
from pyartcd import exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.jira import JIRAClient
from pyartcd.mail import MailService
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from ruamel.yaml import YAML
from tenacity import retry, stop_after_attempt, wait_fixed

_LOGGER = logging.getLogger(__name__)


class PrepareReleasePipeline:
    def __init__(
        self,
        runtime: Runtime,
        group: Optional[str],
        assembly: Optional[str],
        name: Optional[str],
        date: str,
        nightlies: List[str],
        package_owner: str,
        jira_username: str,
        jira_password: str,
        default_advisories: bool = False,
    ) -> None:
        _LOGGER.info("Initializing and verifying parameters...")
        self.runtime = runtime
        self.assembly = assembly or "stream"
        self.release_name = None
        group_match = None
        if group:
            group_match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
            if not group_match:
                raise ValueError(f"Invalid group name: {group}")
        self.group_name = group
        self.candidate_nightlies = {}
        if self.assembly == "stream":
            if not name:
                raise ValueError("Release name is required to prepare a release from stream assembly.")
            self.release_name = name
            self.release_version = tuple(map(int, name.split(".", 2)))
            if group and group != f"openshift-{self.release_version[0]}.{self.release_version[1]}":
                raise ValueError(f"Group name {group} doesn't match release name {name}")
            if self.release_version[0] < 4 and nightlies:
                raise ValueError("No nightly needed for OCP3 releases")
            if self.release_version[0] >= 4 and not nightlies:
                raise ValueError("You need to specify at least one nightly.")
            self.candidate_nightlies = self.parse_nighties(nightlies)
        else:
            if name:
                raise ValueError("Release name cannot be set for a non-stream assembly.")
            if nightlies:
                raise ValueError("Nightlies cannot be specified in job parameter for a non-stream assembly.")
            if not group_match:
                raise ValueError("A valid group is required to prepare a release for a non-stream assembly.")
            self.release_version = (int(group_match[1]), int(group_match[2]), 0)
            if default_advisories:
                raise ValueError("default_advisories cannot be set for a non-stream assembly.")

        self.release_date = date
        self.package_owner = package_owner or self.runtime.config["advisory"]["package_owner"]
        self.working_dir = self.runtime.working_dir.absolute()
        self.default_advisories = default_advisories
        self.dry_run = self.runtime.dry_run
        self.elliott_working_dir = self.working_dir / "elliott-working"
        self.doozer_working_dir = self.working_dir / "doozer-working"
        self._jira_client = JIRAClient.from_url(self.runtime.config["jira"]["url"], (jira_username, jira_password))
        self.mail = MailService.from_config(self.runtime.config)
        # sets environment variables for Elliott and Doozer
        self._ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.doozer_working_dir)
        self._elliott_env_vars = os.environ.copy()
        self._elliott_env_vars["ELLIOTT_WORKING_DIR"] = str(self.elliott_working_dir)
        if self._ocp_build_data_url:
            self._elliott_env_vars["ELLIOTT_DATA_PATH"] = self._ocp_build_data_url
            self._doozer_env_vars["DOOZER_DATA_PATH"] = self._ocp_build_data_url

    async def run(self):
        self.working_dir.mkdir(parents=True, exist_ok=True)
        build_data_repo = self.working_dir / "ocp-build-data-push"
        shutil.rmtree(build_data_repo, ignore_errors=True)
        shutil.rmtree(self.elliott_working_dir, ignore_errors=True)
        shutil.rmtree(self.doozer_working_dir, ignore_errors=True)

        release_config = None
        group_config = await self.load_group_config()

        if self.assembly != "stream":
            releases_config = await self.load_releases_config()
            release_config = releases_config.get("releases", {}).get(self.assembly, {})
            if not release_config:
                raise ValueError(f"Assembly {self.assembly} is not defined in releases.yml for group {self.group_name}.")
            group_config = assembly_group_config(Model(releases_config), self.assembly, Model(group_config)).primitive()
            asssembly_type = release_config.get("assembly", {}).get("type", "standard")
            if asssembly_type == "standard":
                self.release_name = self.assembly
                self.release_version = tuple(map(int, self.release_name.split(".", 2)))
            elif asssembly_type == "custom":
                self.release_name = f"{self.release_version[0]}.{self.release_version[1]}.0-assembly.{self.assembly}"
            elif asssembly_type == "candidate":
                self.release_name = f"{self.release_version[0]}.{self.release_version[1]}.0-{self.assembly}"
            nightlies = release_config.get("assembly", {}).get("basis", {}).get("reference_releases", {}).values()
            self.candidate_nightlies = self.parse_nighties(nightlies)

        if release_config and asssembly_type != "standard":
            _LOGGER.warning("No need to check Blocker Bugs for assembly %s", self.assembly)
        else:
            _LOGGER.info("Checking Blocker Bugs for release %s...", self.release_name)
            self.check_blockers()

        advisories = {}

        if self.default_advisories:
            advisories = group_config.get("advisories", {})
        else:
            _LOGGER.info("Creating advisories for release %s...", self.release_name)
            if release_config:
                advisories = group_config.get("advisories", {}).copy()

            if self.release_version[2] == 0:  # GA release
                if advisories.get("rpm", 0) <= 0:
                    advisories["rpm"] = self.create_advisory("RHEA", "rpm", "ga")
                if advisories.get("image", 0) <= 0:
                    advisories["image"] = self.create_advisory("RHEA", "image", "ga")
            else:  # z-stream release
                if advisories.get("rpm", 0) <= 0:
                    advisories["rpm"] = self.create_advisory("RHBA", "rpm", "standard")
                if advisories.get("image", 0) <= 0:
                    advisories["image"] = self.create_advisory("RHBA", "image", "standard")
            if self.release_version[0] > 3:
                if advisories.get("extras", 0) <= 0:
                    advisories["extras"] = self.create_advisory("RHBA", "image", "extras")
                if advisories.get("metadata", 0) <= 0:
                    advisories["metadata"] = self.create_advisory("RHBA", "image", "metadata")

        advisories_changed = advisories != group_config.get("advisories", {})

        _LOGGER.info("Ensuring JIRA ticket for release %s...", self.release_name)
        jira_issue_key = group_config.get("release_jira")
        jira_template_vars = {
            "release_name": self.release_name,
            "x": self.release_version[0],
            "y": self.release_version[1],
            "z": self.release_version[2],
            "release_date": self.release_date,
            "advisories": advisories,
            "candidate_nightlies": self.candidate_nightlies,
        }
        if jira_issue_key:
            _LOGGER.info("Reusing existing release JIRA %s", jira_issue_key)
            jira_issue = self._jira_client.get_issue(jira_issue_key)
            subtasks = [self._jira_client.get_issue(subtask.key) for subtask in jira_issue.fields.subtasks]
            self.update_release_jira(jira_issue, subtasks, jira_template_vars)
        else:
            _LOGGER.info("Creating a release JIRA...")
            jira_issues = self.create_release_jira(jira_template_vars)
            jira_issue = jira_issues[0] if jira_issues else None
            jira_issue_key = jira_issue.key if jira_issue else None

        _LOGGER.info("Updating ocp-build-data...")
        build_data_changed = await self.update_build_data(advisories, jira_issue_key)

        if advisories_changed or build_data_changed:
            _LOGGER.info("Sending an Errata live ID request email...")
            self.send_live_id_request_mail(advisories)

        _LOGGER.info("Sweep builds into the the advisories...")
        for kind, advisory in advisories.items():
            if not advisory:
                continue
            self.change_advisory_state(advisory, "NEW_FILES")
            if kind == "rpm":
                self.sweep_builds("rpm", advisory)
            elif kind == "image":
                self.sweep_builds(
                    "image", advisory, only_payload=self.release_version[0] >= 4
                )
            elif kind == "extras":
                self.sweep_builds("image", advisory, only_non_payload=True)
            elif kind == "metadata":
                await self.build_and_attach_bundles(advisory)

        # bugs should be swept after builds to have validation
        # for only those bugs to be attached which have corresponding brew builds
        # attached to the advisory
        # currently for rpm advisory and cves only
        _LOGGER.info("Sweep bugs into the the advisories...")
        self.sweep_bugs(check_builds=True)

        _LOGGER.info("Adding placeholder bugs...")
        for kind, advisory in advisories.items():
            bug_ids = get_bug_ids(advisory)
            if not bug_ids:  # Only create placeholder bug if the advisory has no attached bugs
                _LOGGER.info("Create placeholder bug for %s advisory %s...", kind, advisory)
                self.create_and_attach_placeholder_bug(kind, advisory)

        # Verify the swept builds match the nightlies
        if self.release_version[0] < 4:
            _LOGGER.info("Don't verify payloads for OCP3 releases")
        else:
            _LOGGER.info("Verify the swept builds match the nightlies...")
            for _, payload in self.candidate_nightlies.items():
                self.verify_payload(payload, advisories["image"])

        if build_data_changed or self.candidate_nightlies:
            _LOGGER.info("Sending a notification to QE and multi-arch QE...")
            if self.dry_run:
                jira_issue_link = "https://jira.example.com/browse/FOO-1"
            else:
                jira_issue_link = jira_issue.permalink()
            self.send_notification_email(advisories, jira_issue_link)

        # Move advisories to QE
        for kind, advisory in advisories.items():
            try:
                if kind == "metadata":
                    # Verify attached operators
                    await self.verify_attached_operators(advisories["image"], advisories["extras"], advisories["metadata"])
                self.change_advisory_state(advisory, "QE")
            except CalledProcessError as ex:
                _LOGGER.warning(f"Unable to move {kind} advisory {advisory} to QE: {ex}")

    async def load_releases_config(self) -> Dict:
        repo = self.working_dir / "ocp-build-data-push"
        if not repo.exists():
            await self.clone_build_data(repo)
        async with aiofiles.open(repo / "releases.yml", "r") as f:
            content = await f.read()
        yaml = YAML(typ="safe")
        return yaml.load(content)

    async def load_group_config(self) -> Dict:
        repo = self.working_dir / "ocp-build-data-push"
        if not repo.exists():
            await self.clone_build_data(repo)
        async with aiofiles.open(repo / "group.yml", "r") as f:
            content = await f.read()
        yaml = YAML(typ="safe")
        return yaml.load(content)

    @classmethod
    def parse_nighties(cls, nighty_tags: List[str]) -> Dict[str, str]:
        arch_nightlies = {}
        for nightly in nighty_tags:
            if "s390x" in nightly:
                arch = "s390x"
            elif "ppc64le" in nightly:
                arch = "ppc64le"
            elif "arm64" in nightly:
                arch = "aarch64"
            else:
                arch = "x86_64"
            if ":" not in nightly:
                # prepend pullspec URL to nightly name
                # TODO: proper translation facility between brew and go arch nomenclature
                arch_suffix = "" if arch == "x86_64" else "-arm64" if arch == "aarch64" else "-" + arch
                nightly = f"registry.ci.openshift.org/ocp{arch_suffix}/release{arch_suffix}:{nightly}"
            arch_nightlies[arch] = nightly
        return arch_nightlies

    def check_blockers(self):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "find-bugs",
            "--mode=blocker",
            "--exclude-status=ON_QA",
            "--report"
        ]
        if self.runtime.dry_run:
            _LOGGER.warning("[DRY RUN] Would have run %s", cmd)
            return
        _LOGGER.debug("Running command: %s", cmd)
        result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, check=False, universal_newlines=True, cwd=self.working_dir)
        if result.returncode != 0:
            raise IOError(
                f"Command {cmd} returned {result.returncode}: stdout={result.stdout}, stderr={result.stderr}"
            )
        _LOGGER.info(result.stdout)
        match = re.search(r"Found ([0-9]+) bugs", str(result.stdout))
        if match and int(match[1]) != 0:
            _LOGGER.info(f"{int(match[1])} Blocker Bugs found! Make sure to resolve these blocker bugs before proceeding to promote the release.")

    def create_advisory(self, type: str, kind: str, impetus: str) -> int:
        create_cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "create",
            f"--type={type}",
            f"--kind={kind}",
            f"--impetus={impetus}",
            f"--assigned-to={self.runtime.config['advisory']['assigned_to']}",
            f"--manager={self.runtime.config['advisory']['manager']}",
            f"--package-owner={self.package_owner}",
            f"--date={self.release_date}",
        ]
        if not self.dry_run:
            create_cmd.append("--yes")
        _LOGGER.debug("Running command: %s", create_cmd)
        result = subprocess.run(create_cmd, check=False, stdout=PIPE, stderr=PIPE, universal_newlines=True, cwd=self.working_dir)
        if result.returncode != 0:
            raise IOError(
                f"Command {create_cmd} returned {result.returncode}: stdout={result.stdout}, stderr={result.stderr}"
            )
        match = re.search(
            r"https:\/\/errata\.devel\.redhat\.com\/advisory\/([0-9]+)", result.stdout
        )
        advisory_num = int(match[1])
        _LOGGER.info("Created %s advisory %s", impetus, advisory_num)
        return advisory_num

    async def clone_build_data(self, local_path: Path):
        shutil.rmtree(local_path, ignore_errors=True)
        # shallow clone ocp-build-data
        cmd = [
            "git",
            "-C",
            str(self.working_dir),
            "clone",
            "-b",
            self.group_name,
            "--depth=1",
            self.runtime.config["build_config"]["ocp_build_data_repo_push_url"],
            str(local_path),
        ]
        _LOGGER.debug("Running command: %s", cmd)
        await exectools.cmd_assert_async(cmd)

    async def update_build_data(self, advisories: Dict[str, int], jira_issue_key: Optional[str]):
        if not advisories and not jira_issue_key:
            return False
        repo = self.working_dir / "ocp-build-data-push"
        if not repo.exists():
            await self.clone_build_data(repo)

        if not self.assembly or self.assembly == "stream":
            # update advisory numbers in group.yml
            with open(repo / "group.yml", "r") as f:
                group_config = f.read()
            for kind, advisory in advisories.items():
                new_group_config = re.sub(
                    fr"^(\s+{kind}:)\s*[0-9]+$", fr"\1 {advisory}", group_config, count=1, flags=re.MULTILINE
                )
                group_config = new_group_config
            # freeze automation
            group_config = re.sub(r"^freeze_automation:.*", "freeze_automation: scheduled", group_config, count=1, flags=re.MULTILINE)
            # update group.yml
            with open(repo / "group.yml", "w") as f:
                f.write(group_config)
        else:
            # update releases.yml (if we are operating on a non-stream assembly)
            yaml = YAML(typ="rt")
            yaml.preserve_quotes = True
            async with aiofiles.open(repo / "releases.yml", "r") as f:
                old = await f.read()
            releases_config = yaml.load(old)
            group_config = releases_config["releases"][self.assembly].setdefault("assembly", {}).setdefault("group", {})
            group_config["advisories"] = advisories
            group_config["release_jira"] = jira_issue_key
            out = StringIO()
            yaml.dump(releases_config, out)
            async with aiofiles.open(repo / "releases.yml", "w") as f:
                await f.write(out.getvalue())

        cmd = ["git", "-C", str(repo), "--no-pager", "diff"]
        await exectools.cmd_assert_async(cmd)
        cmd = ["git", "-C", str(repo), "add", "."]
        await exectools.cmd_assert_async(cmd)
        cmd = ["git", "-C", str(repo), "diff-index", "--quiet", "HEAD"]
        rc = await exectools.cmd_assert_async(cmd, check=False)
        if rc == 0:
            _LOGGER.warn("Skip saving advisories: No changes.")
            return False
        cmd = ["git", "-C", str(repo), "commit", "-m", f"Prepare release {self.release_name}"]
        await exectools.cmd_assert_async(cmd)
        if not self.dry_run:
            _LOGGER.info("Pushing changes to upstream...")
            cmd = ["git", "-C", str(repo), "push", "origin", self.group_name]
            await exectools.cmd_assert_async(cmd)
        else:
            _LOGGER.warn("Would have run %s", cmd)
            _LOGGER.warn("Would have pushed changes to upstream")
        return True

    def create_and_attach_placeholder_bug(self, kind: str, advisory: int):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "create-placeholder",
            f"--kind={kind}",
            f"--attach={advisory}",
        ]
        _LOGGER.debug("Running command: %s", cmd)
        if self.dry_run:
            _LOGGER.warn("Would have run: %s", cmd)
        else:
            subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    def sweep_bugs(
        self,
        statuses: List[str] = ["MODIFIED", "ON_QA", "VERIFIED"],
        include_cve: bool = True,
        advisory: Optional[int] = None,
        check_builds: bool = False,
    ):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "find-bugs",
            "--mode=sweep",
        ]
        if include_cve:
            cmd.append("--cve-trackers")
        if check_builds:
            cmd.append("--check-builds")
        for status in statuses:
            cmd.append("--status=" + status)
        if advisory:
            cmd.append(f"--add={advisory}")
        else:
            cmd.append("--into-default-advisories")
        if self.dry_run:
            cmd.append("--dry-run")
        _LOGGER.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    def sweep_builds(
        self, kind: str, advisory: int, only_payload=False, only_non_payload=False
    ):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "find-builds",
            f"--kind={kind}",
        ]
        if only_payload:
            cmd.append("--payload")
        if only_non_payload:
            cmd.append("--non-payload")
        if not self.dry_run:
            cmd.append(f"--attach={advisory}")
        _LOGGER.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)

    def change_advisory_state(self, advisory: int, state: str):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "change-state",
            "-s",
            state,
            "-a",
            str(advisory),
        ]
        if self.dry_run:
            cmd.append("--dry-run")
        _LOGGER.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        _LOGGER.info("Moved advisory %d to %s", advisory, state)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    def verify_payload(self, pullspec: str, advisory: int):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "verify-payload",
            f"{pullspec}",
            f"{advisory}",
        ]
        if self.dry_run:
            _LOGGER.info("Would have run: %s", cmd)
            return
        _LOGGER.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        # elliott verify-payload always writes results to $cwd/"summary_results.json".
        # move it to a different location to avoid overwritting the result.
        results_path = self.working_dir / "summary_results.json"
        new_path = self.working_dir / f"verify-payload-results-{pullspec.split(':')[-1]}.json"
        shutil.move(results_path, new_path)
        with open(new_path, "r") as f:
            results = json.load(f)
            if results.get("missing_in_advisory") or results.get("payload_advisory_mismatch"):
                raise ValueError(f"""Failed to verify payload for nightly {pullspec}.
Please fix advisories and nightlies to match each other, manually verify them with `elliott verify-payload`,
update JIRA accordingly, then notify QE and multi-arch QE for testing.""")

    def create_release_jira(self, template_vars: Dict):
        template_issue_key = self.runtime.config["jira"]["templates"][f"ocp{self.release_version[0]}"]

        _LOGGER.info("Creating release JIRA from template %s...",
                     template_issue_key)

        template_issue = self._jira_client.get_issue(template_issue_key)

        def fields_transform(fields):
            labels = set(fields.get("labels", []))
            # change summary title for security
            if "template" not in labels:
                return fields  # no need to modify fields of non-template issue
            # remove "template" label
            fields["labels"] = list(labels - {"template"})
            return self._render_jira_template(fields, template_vars)
        if self.dry_run:
            fields = fields_transform(template_issue.raw["fields"].copy())
            _LOGGER.warning(
                "[DRY RUN] Would have created release JIRA: %s", fields["summary"])
            return []
        new_issues = self._jira_client.clone_issue_with_subtasks(
            template_issue, fields_transform=fields_transform)
        _LOGGER.info("Created release JIRA: %s", new_issues[0].permalink())
        return new_issues

    @staticmethod
    def _render_jira_template(fields: Dict, template_vars: Dict):
        fields.copy()
        try:
            fields["summary"] = jinja2.Template(fields["summary"]).render(template_vars)
        except jinja2.TemplateSyntaxError as ex:
            _LOGGER.warning("Failed to render JIRA template text: %s", ex)
        try:
            fields["description"] = jinja2.Template(fields["description"]).render(template_vars)
        except jinja2.TemplateSyntaxError as ex:
            _LOGGER.warning("Failed to render JIRA template text: %s", ex)
        return fields

    def update_release_jira(self, issue: Issue, subtasks: List[Issue], template_vars: Dict[str, int]):
        template_issue_key = self.runtime.config["jira"]["templates"][f"ocp{self.release_version[0]}"]
        _LOGGER.info("Updating release JIRA %s from template %s...", issue.key, template_issue_key)
        template_issue = self._jira_client.get_issue(template_issue_key)
        old_fields = {
            "summary": issue.fields.summary,
            "description": issue.fields.description,
        }
        fields = {
            "summary": template_issue.fields.summary,
            "description": template_issue.fields.description,
        }
        if "template" in template_issue.fields.labels:
            fields = self._render_jira_template(fields, template_vars)
        jira_changed = fields != old_fields
        if not self.dry_run:
            issue.update(fields)
        else:
            _LOGGER.warning("Would have updated JIRA ticket %s with summary %s", issue.key, fields["summary"])

        _LOGGER.info("Updating subtasks for release JIRA %s...", issue.key)
        template_subtasks = [self._jira_client.get_issue(subtask.key) for subtask in template_issue.fields.subtasks]
        if len(subtasks) != len(template_subtasks):
            _LOGGER.warning("Release JIRA %s has different number of subtasks from the template ticket %s. Subtasks will not be updated.", issue.key, template_issue.key)
            return
        for subtask, template_subtask in zip(subtasks, template_subtasks):
            fields = {
                "summary": template_subtask.fields.summary,
                "description": template_subtask.fields.description,
            }
            if "template" in template_subtask.fields.labels:
                fields = self._render_jira_template(fields, template_vars)
            if not self.dry_run:
                subtask.update(fields)
            else:
                _LOGGER.warning("Would have updated JIRA ticket %s with summary %s", subtask.key, fields["summary"])

        return jira_changed

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    async def build_and_attach_bundles(self, metadata_advisory: int):
        _LOGGER.info("Finding OLM bundles (will rebuild if not present)...")
        cmd = [
            "doozer",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "olm-bundle:rebase-and-build",
        ]
        if self.dry_run:
            cmd.append("--dry-run")
        _LOGGER.debug("Running command: %s", cmd)
        await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars, cwd=self.working_dir)
         # parse record.log
        with open(self.doozer_working_dir / "record.log", "r") as file:
            record_log = parse_record_log(file)
        bundle_nvrs = [record["bundle_nvr"] for record in record_log["build_olm_bundle"] if record["status"] == "0"]

        if not bundle_nvrs:
            return
        _LOGGER.info("Attaching bundle builds %s to advisory %s...", bundle_nvrs, metadata_advisory)
        cmd = [
            "elliott",
            f"--group={self.group_name}",
            "--assembly", self.assembly,
            "find-builds",
            f"--kind=image",
        ]
        for bundle_nvr in bundle_nvrs:
            cmd.append("--build")
            cmd.append(bundle_nvr)
        if not self.dry_run and metadata_advisory:
            cmd.append(f"--attach")
            cmd.append(f"{metadata_advisory}")
        _LOGGER.debug("Running command: %s", cmd)
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, cwd=self.working_dir)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    async def verify_attached_operators(self, *advisories: List[int]):
        cmd = [
            "elliott",
            f"--group={self.group_name}",
            f"--assembly={self.assembly}",
            "verify-attached-operators",
            "--"
        ]
        for advisory in advisories:
            cmd.append(f"{advisory}")
        _LOGGER.debug("Running command: %s", cmd)
        await exectools.cmd_assert_async(cmd, env=self._elliott_env_vars, cwd=self.working_dir)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    def send_live_id_request_mail(self, advisories: Dict[str, int]):
        subject = f"Live IDs for {self.release_name}"
        main_advisory = "image" if self.release_version[0] >= 4 else "rpm"
        content = f"""Hello docs team,

ART would like to request Live IDs for our {self.release_name} advisories:
{main_advisory}: https://errata.devel.redhat.com/advisory/{advisories[main_advisory]}

This is the current set of advisories we intend to ship:
"""
        for kind, advisory in advisories.items():
            content += (
                f"- {kind}: https://errata.devel.redhat.com/advisory/{advisory}\n"
            )

        email_dir = self.working_dir / "email"
        self.mail.send_mail(self.runtime.config["email"]["live_id_request_recipients"], subject, content, archive_dir=email_dir, dry_run=self.dry_run)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(10))
    def send_notification_email(self, advisories: Dict[str, int], jira_link: str):
        subject = f"OCP {self.release_name} advisories and nightlies"
        content = f"This is the current set of advisories for {self.release_name}:\n"
        for kind, advisory in advisories.items():
            content += (
                f"- {kind}: https://errata.devel.redhat.com/advisory/{advisory}\n"
            )
        if self.candidate_nightlies:
            content += "\nNightlies:\n"
            for arch, pullspec in self.candidate_nightlies.items():
                content += f"- {arch}: {pullspec}\n"
        content += f"\nJIRA ticket: {jira_link}\n"
        content += "\nThanks.\n"
        email_dir = self.working_dir / "email"
        self.mail.send_mail(self.runtime.config["email"][f"prepare_release_notification_recipients_ocp{self.release_version[0]}"], subject, content, archive_dir=email_dir, dry_run=self.dry_run)


@cli.command("prepare-release")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True, default="stream",
              help="The name of an assembly to rebase & build for. e.g. 4.9.1")
@click.option("--name", metavar="RELEASE_NAME",
              help="release name (e.g. 4.6.42)")
@click.option("--date", metavar="YYYY-MMM-DD", required=True,
              help="Expected release date (e.g. 2020-11-25)")
@click.option("--package-owner", metavar='EMAIL',
              help="Advisory package owner; Must be an individual email address; May be anyone who wants random advisory spam")
@click.option("--nightly", "nightlies", metavar="TAG", multiple=True,
              help="[MULTIPLE] Candidate nightly")
@click.option("--default-advisories", is_flag=True,
              help="don't create advisories/jira; pick them up from ocp-build-data")
@pass_runtime
@click_coroutine
async def rebuild(runtime: Runtime, group: str, assembly: str, name: Optional[str], date: str,
                  package_owner: Optional[str], nightlies: Tuple[str, ...], default_advisories: bool):
    # parse environment variables for credentials
    jira_username = os.environ.get("JIRA_USERNAME")
    jira_password = os.environ.get("JIRA_PASSWORD")
    if not jira_username:
        raise ValueError("JIRA_USERNAME environment variable is not set")
    if not jira_password:
        raise ValueError("JIRA_PASSWORD environment variable is not set")
    # start pipeline
    pipeline = PrepareReleasePipeline(
        runtime=runtime,
        group=group,
        assembly=assembly,
        name=name,
        date=date,
        nightlies=nightlies,
        package_owner=package_owner,
        jira_username=jira_username,
        jira_password=jira_password,
        default_advisories=default_advisories,
    )
    await pipeline.run()
