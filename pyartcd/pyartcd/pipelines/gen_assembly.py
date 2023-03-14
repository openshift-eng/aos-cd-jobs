import logging
import os
import re
import traceback
from collections import namedtuple
from io import StringIO
from typing import Iterable, Optional, OrderedDict, Tuple

import click
from ghapi.all import GhApi
from pyartcd import exectools, constants
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.git import GitRepository
from pyartcd.runtime import Runtime
from ruamel.yaml import YAML

yaml = YAML(typ="rt")
yaml.preserve_quotes = True


def _merge(a, b):
    """ Merges two, potentially deep, objects into a new one and returns the result.
    'a' is layered over 'b' and is dominant when necessary. The output is 'c'.
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a
    c: OrderedDict = b.copy()
    for k, v in a.items():
        c[k] = _merge(v, b.get(k))
        if k not in b:
            # move new entry to the beginning
            c.move_to_end(k, last=False)
    return c


class GenAssemblyPipeline:
    """ Rebase and build MicroShift for an assembly """

    def __init__(self, runtime: Runtime, group: str, assembly: str, ocp_build_data_url: str,
                 nightlies: Tuple[str, ...], allow_pending: bool, allow_rejected: bool, allow_inconsistency: bool,
                 custom: bool, arches: Tuple[str, ...], in_flight: Optional[str], previous_list: Tuple[str, ...], auto_previous: bool,
                 logger: Optional[logging.Logger] = None):
        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.nightlies = nightlies
        self.allow_pending = allow_pending
        self.allow_rejected = allow_rejected
        self.allow_inconsistency = allow_inconsistency
        self.custom = custom
        self.arches = arches
        self.in_flight = in_flight
        self.previous_list = previous_list
        self.auto_previous = auto_previous
        self._logger = logger or runtime.logger
        self._slack_client = self.runtime.new_slack_client()
        self._working_dir = self.runtime.working_dir.absolute()

        self._github_token = os.environ.get('GITHUB_TOKEN')
        if not self._github_token and not self.runtime.dry_run:
            raise ValueError("GITHUB_TOKEN environment variable is required to create a pull request.")

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
        if not match:
            raise ValueError(f"Invalid group name: {group}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self._working_dir / "doozer-working")

        if not ocp_build_data_url:
            ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        if ocp_build_data_url:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = ocp_build_data_url

    async def run(self):
        self._slack_client.bind_channel(self.group)
        slack_response = await self._slack_client.say(f":construction: Generating assembly definition {self.assembly} :construction:")
        slack_thread = slack_response["message"]["ts"]
        try:
            if self.arches and not self.custom:
                raise ValueError("Customizing arches can only be used with custom assemblies.")

            if self.custom and (self.auto_previous or self.previous_list or self.in_flight):
                raise ValueError("Specifying previous list for a custom release is not allowed.")

            self._logger.info("Getting nightlies from Release Controllers...")
            candidate_nightlies = await self._get_nightlies()
            self._logger.info("Generating assembly definition...")
            assembly_definition = await self._gen_assembly_from_releases(candidate_nightlies)
            out = StringIO()
            yaml.dump(assembly_definition, out)
            self._logger.info("Generated assembly definition:\n%s", out.getvalue())

            # Create a PR
            pr = await self._create_or_update_pull_request(assembly_definition)

            # Sends a slack message
            message = f"Hi @release-artists , please review assembly definition for {self.assembly}: {pr.html_url}"
            await self._slack_client.say(message, slack_thread)
        except Exception as err:
            error_message = f"Error generating assembly definition: {err}\n {traceback.format_exc()}"
            self._logger.error(error_message)
            await self._slack_client.say(error_message, slack_thread)
            raise

    async def _get_nightlies(self):
        """ Get nightlies from Release Controllers
        :param release: release field for rebase
        :return: NVRs
        """
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", "stream",
        ]
        if self.arches:
            cmd.append("--arches")
            cmd.append(",".join(self.arches))
        cmd.append("get-nightlies")
        if self.allow_pending:
            cmd.append("--allow-pending")
        if self.allow_rejected:
            cmd.append("--allow-rejected")
        if self.allow_inconsistency:
            cmd.append("--allow-inconsistency")
        for nightly in self.nightlies:
            cmd.append(f"--matching={nightly}")

        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=self._doozer_env_vars)
        return out.strip().split()

    async def _gen_assembly_from_releases(self, candidate_nightlies: Iterable[str]) -> OrderedDict:
        """ Run doozer release:gen-assembly from-releases
        :return: Assembly definition
        """
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", "stream",
        ]
        if self.arches:
            cmd.append("--arches")
            cmd.append(",".join(self.arches))
        cmd.append("release:gen-assembly")
        cmd.append(f"--name={self.assembly}")
        cmd.append("from-releases")
        for nightly in candidate_nightlies:
            cmd.append(f"--nightly={nightly}")
        if self.custom:
            cmd.append("--custom")
        else:
            if self.in_flight:
                cmd.append(f"--in-flight={self.in_flight}")
            for previous in self.previous_list:
                cmd.append(f"--previous={previous}")
            if self.auto_previous:
                cmd.append("--auto-previous")
        _, out, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=self._doozer_env_vars)
        return yaml.load(out)

    async def _create_or_update_pull_request(self, assembly_definition: OrderedDict):
        """ Create or update pull request for ocp-build-data
        :param assembly_definition: the assembly definition to be added to releases.yml
        """
        self._logger.info("Creating ocp-build-data PR...")
        # Clone ocp-build-data
        build_data_path = self._working_dir / "ocp-build-data-push"
        build_data = GitRepository(build_data_path, dry_run=self.runtime.dry_run)
        ocp_build_data_repo_push_url = self.runtime.config["build_config"]["ocp_build_data_repo_push_url"]
        await build_data.setup(ocp_build_data_repo_push_url)
        branch = f"auto-gen-assembly-{self.group}-{self.assembly}"
        await build_data.fetch_switch_branch(branch, self.group)
        # Load releases.yml
        releases_yaml_path = build_data_path / "releases.yml"
        releases_yaml = yaml.load(releases_yaml_path) if releases_yaml_path.exists() else {}
        # Make changes
        releases_yaml = _merge(assembly_definition, releases_yaml)
        yaml.dump(releases_yaml, releases_yaml_path)
        # Create a PR
        title = f"Add assembly {self.assembly}"
        body = f"Created by job run {self.runtime.get_job_run_url()}"
        match = re.search(r"github\.com[:/](.+)/(.+)(?:.git)?", ocp_build_data_repo_push_url)
        if not match:
            raise ValueError(f"Couldn't create a pull request: {ocp_build_data_repo_push_url} is not a valid github repo")
        head = f"{match[1]}:{branch}"
        base = self.group
        if self.runtime.dry_run:
            self._logger.warning("[DRY RUN] Would have created pull-request with head '%s', base '%s' title '%s', body '%s'", head, base, title, body)
            d = {"html_url": "https://github.example.com/foo/bar/pull/1234", "number": 1234}
            result = namedtuple('pull_request', d.keys())(*d.values())
            return result
        pushed = await build_data.commit_push(f"{title}\n{body}")
        result = None
        if pushed:
            owner = "openshift-eng"
            repo = "ocp-build-data"
            api = GhApi(owner=owner, repo=repo, token=self._github_token)
            existing_prs = api.pulls.list(state="open", base=base, head=head)
            if not existing_prs.items:
                result = api.pulls.create(head=head, base=base, title=title, body=body, maintainer_can_modify=True)
            else:
                pull_number = existing_prs.items[0].number
                result = api.pulls.update(pull_number=pull_number, title=title, body=body)
        else:
            self._logger.warning("PR is not created: Nothing to commit.")
        return result


@cli.command("gen-assembly")
@click.option("--data-path", metavar='BUILD_DATA', default=None,
              help=f"Git repo or directory containing groups metadata e.g. {constants.OCP_BUILD_DATA_URL}")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly to generate for. e.g. 4.9.1")
@click.option("--nightly", "nightlies", metavar="TAG", multiple=True,
              help="(Optional) [MULTIPLE] List of nightlies to match with `doozer get-nightlies` (if empty, find latest)")
@click.option("--allow-pending", is_flag=True,
              help="Match nightlies that have not completed tests")
@click.option("--allow-rejected", is_flag=True,
              help="Match nightlies that have failed their tests")
@click.option("--allow-inconsistency", is_flag=True,
              help="Allow matching nightlies built from matching commits but with inconsistent RPMs")
@click.option("--custom", is_flag=True,
              help="Custom assemblies are not for official release. They can, for example, not have all required arches for the group.")
@click.option("--arch", "arches", metavar="TAG", multiple=True,
              help="(Optional) [MULTIPLE] (for custom assemblies only) Limit included arches to this list")
@click.option('--in-flight', 'in_flight', metavar='EDGE', help='An in-flight release that can upgrade to this release')
@click.option('--previous', 'previous_list', metavar='EDGES', default=[], multiple=True, help='A list of releases that can upgrade to this release')
@click.option('--auto-previous', 'auto_previous', is_flag=True, help='If specified, previous list is calculated from Cincinnati graph')
@pass_runtime
@click_coroutine
async def gen_assembly(runtime: Runtime, data_path: str, group: str, assembly: str, nightlies: Tuple[str, ...],
                       allow_pending: bool, allow_rejected: bool, allow_inconsistency: bool, custom: bool, arches: Tuple[str, ...], in_flight: Optional[str],
                       previous_list: Tuple[str, ...], auto_previous: bool):
    pipeline = GenAssemblyPipeline(runtime=runtime, group=group, assembly=assembly, ocp_build_data_url=data_path,
                                   nightlies=nightlies, allow_pending=allow_pending, allow_rejected=allow_rejected, allow_inconsistency=allow_inconsistency,
                                   arches=arches, custom=custom, in_flight=in_flight, previous_list=previous_list, auto_previous=auto_previous)
    await pipeline.run()
