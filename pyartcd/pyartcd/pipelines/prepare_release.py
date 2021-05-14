import argparse
import json
import logging
import os
import re
import shutil
import subprocess
from subprocess import PIPE
from argparse import ArgumentError
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
import toml
from pyartcd.jira import JIRAClient
from pyartcd.mail import MailService

_LOGGER = logging.getLogger(__name__)


class PrepareReleasePipeline:
    def __init__(
        self,
        name: str,
        date: str,
        nightlies: List[str],
        package_owner: str,
        config: Dict[str, Any],
        working_dir: str,
        jira_username: str,
        jira_password: str,
        dry_run: bool=False,
    ) -> None:
        _LOGGER.info("Initializing and verifying parameters...")
        self.config = config
        self.release_name = name
        self.release_date = date
        self.package_owner = package_owner or self.config["advisory"]["package_owner"]
        self.working_dir = Path(working_dir).absolute()
        self.dry_run = dry_run
        self.release_version = tuple(map(int, self.release_name.split(".", 2)))
        self.group_name = (
            f"openshift-{self.release_version[0]}.{self.release_version[1]}"
        )
        self.candidate_nightlies = {}
        if self.release_version[0] < 4 and nightlies:
            _LOGGER.warn("No nightly needed for OCP3 releases")
        if self.release_version[0] >= 4 and not nightlies:
            raise ArgumentError("You need to specify at least one nightly.")
        for nightly in nightlies:
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
                arch_suffix = "" if arch == "x86_64" else "-amd64" if arch == "aarch64" else "-" + arch
                nightly = f"registry.ci.openshift.org/ocp{arch_suffix}/release{arch_suffix}:{nightly}"
            self.candidate_nightlies[arch] = nightly
        self.elliott_working_dir = self.working_dir / "elliott-working"
        self._jira_client = JIRAClient.from_url(config["jira"]["url"], (jira_username, jira_password))
        self.mail = MailService.from_config(config)

    def run(self):
        self.working_dir.mkdir(parents=True, exist_ok=True)

        _LOGGER.info("Checking Blocker Bugs for release %s...", self.release_name)
        self.check_blockers()

        _LOGGER.info("Creating advisories for release %s...",
                     self.release_name)
        advisories = {}
        if self.release_version[2] == 0:  # GA release
            advisories["rpm"] = self.create_advisory("RHEA", "rpm", "ga")
            advisories["image"] = self.create_advisory("RHEA", "image", "ga")
        else:  # z-stream release
            advisories["rpm"] = self.create_advisory("RHBA", "rpm", "standard")
            advisories["image"] = self.create_advisory(
                "RHBA", "image", "standard")
        if self.release_version[0] > 3:
            advisories["extras"] = self.create_advisory(
                "RHBA", "image", "extras")
            advisories["metadata"] = self.create_advisory(
                "RHBA", "image", "metadata")
        _LOGGER.info("Created advisories: %s", advisories)

        _LOGGER.info("Saving the advisories to ocp-build-data...")
        self.save_advisories(advisories)

        _LOGGER.info("Sending an Errata live ID request email...")
        self.send_live_id_request_mail(advisories)

        _LOGGER.info("Creating a release JIRA...")
        jira_issues = self.create_release_jira(advisories)

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

        # bugs should be swept after builds to have validation
        # for only those bugs to be attached which have corresponding brew builds
        # attached to the advisory
        # currently for rpm advisory and cves only
        _LOGGER.info("Sweep bugs into the the advisories...")
        self.sweep_bugs(check_builds=True)

        _LOGGER.info("Adding placeholder bugs to the advisories...")
        for kind, advisory in advisories.items():
            # don't create placeholder bugs for OCP 4 image advisory and OCP 3 rpm advisory
            if (
                not advisory
                or self.release_version[0] >= 4
                and kind == "image"
                or self.release_version[0] < 4
                and kind == "rpm"
            ):
                continue
            self.create_and_attach_placeholder_bug(kind, advisory)

        # Verify the swept builds match the nightlies
        if self.release_version[0] < 4:
            _LOGGER.info("Don't verify payloads for OCP3 releases")
        else:
            _LOGGER.info("Verify the swept builds match the nightlies...")
            for _, payload in self.candidate_nightlies.items():
                self.verify_payload(payload, advisories["image"])

        _LOGGER.info("Sending a notification to QE and multi-arch QE:")
        if self.dry_run:
            jira_issue_link = "https://jira.example.com/browse/FOO-1"
        else:
            jira_issue_link = jira_issues[0].permalink()
        self.send_notification_email(advisories, jira_issue_link)

    def check_blockers(self):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "find-bugs",
            "--mode=blocker",
            "--exclude-status=ON_QA",
            "--report"
        ]
        _LOGGER.debug("Running command: %s", cmd)
        result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, check=True, universal_newlines=True, cwd=self.working_dir)
        _LOGGER.info(result.stdout)
        match = re.search(r"Found ([0-9]+) bugs", str(result.stdout))
        if match and int(match[1]) != 0:
            _LOGGER.info(f"{int(match[1])} Blocker Bugs found! Make sure to resolve these blocker bugs before proceeding to promote the release.")
    
    def create_advisory(self, type: str, kind: str, impetus: str) -> int:
        create_cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "create",
            f"--type={type}",
            f"--kind={kind}",
            f"--impetus={impetus}",
            f"--assigned-to={self.config['advisory']['assigned_to']}",
            f"--manager={self.config['advisory']['manager']}",
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
        return advisory_num

    def save_advisories(self, advisories: Dict[str, int]):
        if not advisories:
            return
        repo = self.working_dir / "ocp-build-data-push"
        shutil.rmtree(repo, ignore_errors=True)
        # shallow clone ocp-build-data
        cmd = [
            "git",
            "-C",
            self.working_dir,
            "clone",
            "-b",
            self.group_name,
            "--depth=1",
            self.config["build_config"]["ocp_build_data_repo_push_url"],
            "ocp-build-data-push",
        ]
        _LOGGER.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        # update advisory numbers
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
        cmd = ["git", "-C", repo, "add", "."]
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        cmd = ["git", "-C", repo, "commit", "-m",
               "Update advisories and freeze automation on group.yml"]
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        if not self.dry_run:
            _LOGGER.info("Pushing changes to upstream...")
            cmd = ["git", "-C", repo, "push", "origin", self.group_name]
            subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        else:
            _LOGGER.warn("Would have run %s", cmd)
            _LOGGER.warn("Would have pushed changes to upstream")

    def create_and_attach_placeholder_bug(self, kind: str, advisory: int):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
            "create-placeholder",
            f"--kind={kind}",
            f"--attach={advisory}",
        ]
        _LOGGER.debug("Running command: %s", cmd)
        if self.dry_run:
            _LOGGER.warn("Would have run: %s", cmd)
        else:
            subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)

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

    def sweep_builds(
        self, kind: str, advisory: int, only_payload=False, only_non_payload=False
    ):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
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

    def verify_payload(self, pullspec: str, advisory: int):
        cmd = [
            "elliott",
            f"--working-dir={self.elliott_working_dir}",
            f"--group={self.group_name}",
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

    def create_release_jira(self, advisories: Dict[str, int]):
        template_issue_key = self.config["jira"]["templates"][f"ocp{self.release_version[0]}"]

        _LOGGER.info("Creating release JIRA from template %s...",
                     template_issue_key)

        template_issue = self._jira_client.get_issue(template_issue_key)

        def fields_transform(fields):
            labels = set(fields.get("labels", []))
            # change summary title for security
            if fields.get("summary"):
                if "product security" in fields["summary"]:
                    fields["summary"] = f"{self.release_name} [{self.release_date}]" + fields["summary"]
            if "template" not in labels:
                return fields  # no need to modify fields of non-template issue
            # remove "template" label
            fields["labels"] = list(labels - {"template"})
            if fields.get("summary"):
                fields["summary"] = f"Release {self.release_name} [{self.release_date}]"
            if fields.get("description"):
                template = jinja2.Template(fields["description"])
                fields["description"] = template.render(
                    advisories=advisories,
                    release_date=self.release_date,
                    candiate_nightlies=self.candidate_nightlies,
                ).strip()
            return fields
        if self.dry_run:
            fields = fields_transform(template_issue.raw["fields"].copy())
            _LOGGER.info(
                "Would have created release JIRA %s", fields["summary"])
            return []
        new_issues = self._jira_client.clone_issue_with_subtasks(
            template_issue, fields_transform=fields_transform)
        _LOGGER.info("Created release JIRA: %s", new_issues[0].permalink())
        return new_issues

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
        self.mail.send_mail(self.config["email"]["live_id_request_recipients"], subject, content, archive_dir=email_dir, dry_run=self.dry_run)

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
        self.mail.send_mail(self.config["email"]["prepare_release_notification_recipients"], subject, content, archive_dir=email_dir, dry_run=self.dry_run)


def main(args):
    # parse command line arguments
    parser = argparse.ArgumentParser("prepare-release")
    parser.add_argument("name", help="release name (e.g. 4.6.42)")
    parser.add_argument(
        "--date", required=True, help="expected release date (e.g. 2020-11-25)"
    )
    parser.add_argument(
        "--nightly",
        dest="nightlies",
        action="append",
        default=[],
        help="[MULTIPLE] candidate nightly",
    )
    parser.add_argument(
        "--package-owner",
        default="lmeyer@redhat.com",
        help="Must be an individual email address; may be anyone who wants random advisory spam",
    )
    parser.add_argument("-c", "--config", required=True,
                        help="configuration file")
    parser.add_argument(
        "-C", "--working-dir", default=".", help="set working directory"
    )
    parser.add_argument(
        "-v", "--verbosity", action="count", help="[MULTIPLE] increase output verbosity"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="don't actually prepare a new release; just print what would be done",
    )
    opts = parser.parse_args(args)

    # parse environment variables for credentials
    jira_username = os.environ.get("JIRA_USERNAME")
    jira_password = os.environ.get("JIRA_PASSWORD")
    if not jira_username:
        raise ValueError("JIRA_USERNAME environment variable is not set")
    if not jira_password:
        raise ValueError("JIRA_PASSWORD environment variable is not set")

    # configure logging
    if not opts.verbosity:
        logging.basicConfig(level=logging.WARNING)
    elif opts.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    elif opts.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)

    # parse configuration file
    with open(opts.config, "r") as config_file:
        config = toml.load(config_file)

    # start pipeline
    pipeline = PrepareReleasePipeline(
        name=opts.name,
        date=opts.date,
        nightlies=opts.nightlies,
        package_owner=opts.package_owner,
        config=config,
        working_dir=opts.working_dir,
        jira_username=jira_username,
        jira_password=jira_password,
        dry_run=opts.dry_run,
    )
    pipeline.run()
    return 0
