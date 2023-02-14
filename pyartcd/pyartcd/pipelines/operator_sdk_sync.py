import os
import re
import subprocess

import click
import koji
import yaml
from errata_tool import Erratum
from pyartcd import constants, util
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime
from doozerlib.util import brew_arch_for_go_arch


class OperatorSDKPipeline:
    def __init__(self, runtime: Runtime, group: str, assembly: str, nvr: str, prerelease: bool, updatelatest: bool, force: bool, arches: str) -> None:
        self.runtime = runtime
        self._logger = runtime.logger
        self.assembly = assembly
        self.prerelease = prerelease
        self.nvr = nvr
        self.updatelatest = updatelatest
        self.sdk = "operator-sdk"
        self.group = group
        self.extra_ad_id = ""
        self.parent_jira_key = ""
        self._jira_client = runtime.new_jira_client()
        self.arches = arches
        self.force = force

    async def run(self):
        if self.nvr:
            build = koji.ClientSession(constants.BREW_SERVER).getBuild(self.nvr)
        else:
            if not self.assembly:
                # Use latest version on cincinnati candidate channel created by promote job
                # like https://github.com/openshift/cincinnati-graph-data/blob/master/channels/candidate-4.12.yaml
                self._logger.info("No assemblly or nvr provided, will use latest candidate")
                github_client = self.runtime.new_github_client()
                candidate_content = github_client.get_repo("openshift/cincinnati-graph-data").get_contents(f"channels/candidate-{self.group}.yaml", ref="master")
                self.assembly = yaml.load(candidate_content.decoded_content, Loader=yaml.FullLoader)['versions'][-1]
            # Use assembly to get jira id and advisory id
            group_config = await util.load_group_config(self.group, self.assembly, env=os.environ.copy())
            self.extra_ad_id = group_config.get("advisories", {}).get("extras", 0)
            self.parent_jira_key = group_config.get("release_jira")
            advisory = Erratum(errata_id=self.extra_ad_id)
            self._logger.info("Check advisory status ...")
            if advisory.errata_state in ["QE", "NEW_FILES"]:
                raise ValueError("Advisory status not in REL_PREP yet ...")
            if advisory.errata_state == "SHIPPED_LIVE":
                self._logger.info("Advisory status already in SHIPPED_LIVE, update subtask 9 ...")
                self._jira_client.complete_subtask(self.parent_jira_key, 8, "Advisory status already in SHIPPED_LIVE", self.force)
            self._logger.info("Advisory status already in post REL_PREP, update subtask 7 ...")
            self._jira_client.complete_subtask(self.parent_jira_key, 6, "Advisory status already in REL_PREP", self.force)

            sdk_build = [b for b in sum(list(map(list, advisory.errata_builds.values())), []) if b.startswith('openshift-enterprise-operator-sdk-container')]
            if not sdk_build:
                self._logger.info("No SDK build to ship, update subtask 8 then close ...")
                self._jira_client.complete_subtask(self.parent_jira_key, 7, f"No SDK build to ship, operator_sdk_sync job: {self.runtime.get_job_run_url()}", self.force)
                return
            # check if sync sdk subtask already done
            parent_jira = self._jira_client.get_issue(self.parent_jira_key)
            sdk_subtask = self._jira_client.get_issue(parent_jira.fields.subtasks[7].key)
            if sdk_subtask.fields.status.name == "Closed":
                # check if already synced
                output = subprocess.getoutput(f"curl -s {constants.OPERATOR_MIRROR_URL}/{self.assembly}/ |grep 'File not found'")
                if not output:
                    self._logger.info("SDK build already sync to mirror, url path with this assembly exist on mirror")
                    if self.force:
                        self._logger.info("Even SDK build already sync to mirror, still force update.")
                    else:
                        return
            build = koji.ClientSession(constants.BREW_SERVER).getBuild(sdk_build[0])

        sdkVersion = self._get_sdkversion(build['extra']['image']['index']['pull'][0])
        self._logger.info(sdkVersion)
        for arch in self.arches.split(','):
            self._extract_binaries(arch, sdkVersion, build['extra']['image']['index']['pull'][0])
        if self.assembly:
            self._jira_client.complete_subtask(self.parent_jira_key, 7, f"operator_sdk_sync job: {self.runtime.get_job_run_url()}", self.force)

    def _get_sdkversion(self, build):
        output = subprocess.getoutput(f"oc image info --filter-by-os amd64 -o json {build} | jq .digest")
        shasum = re.findall("sha256:\\w*", output)[0]
        cmd = f"oc image extract {constants.OPERATOR_URL}@{shasum} --path /usr/local/bin/{self.sdk}:. --confirm && chmod +x {self.sdk} && ./{self.sdk} version && rm {self.sdk}"
        self._logger.info(cmd)
        sdkvalue = subprocess.getoutput(cmd)
        sdkversion = re.findall("v\\d.*-ocp", sdkvalue)[0]
        return sdkversion

    def _extract_binaries(self, arch, sdkVersion, build):
        output = subprocess.getoutput(f"oc image info --filter-by-os {arch} -o json {build} | jq .digest")
        shasum = re.findall("sha256:\\w*", output)[0]

        rarch = brew_arch_for_go_arch(arch)
        tarballFilename = f"{self.sdk}-{sdkVersion}-linux-{rarch}.tar.gz"

        cmd = f"rm -rf ./{rarch} && mkdir ./{rarch}" + \
              f" && oc image extract {constants.OPERATOR_URL}@{shasum} --path /usr/local/bin/{self.sdk}:./{rarch}/ --confirm" + \
              f" && chmod +x ./{rarch}/{self.sdk} && tar -c --preserve-order -z -v --file ./{rarch}/{tarballFilename} ./{rarch}/{self.sdk}" + \
              f" && ln -s {tarballFilename} ./{rarch}/{self.sdk}-linux-{rarch}.tar.gz && rm -f ./{rarch}/{self.sdk}"
        self.exec_cmd(cmd)
        if arch == 'amd64':
            tarballFilename = f"{self.sdk}-{sdkVersion}-darwin-{rarch}.tar.gz"
            cmd = f"oc image extract {constants.OPERATOR_URL}@{shasum} --path /usr/share/{self.sdk}/mac/{self.sdk}:./{rarch}/ --confirm" + \
                  f" && chmod +x ./{rarch}/{self.sdk} && tar -c --preserve-order -z -v --file ./{rarch}/{tarballFilename} ./{rarch}/{self.sdk}" + \
                  f" && ln -s {tarballFilename} ./{rarch}/{self.sdk}-darwin-{rarch}.tar.gz && rm -f ./{rarch}/{self.sdk}"
            self.exec_cmd(cmd)
        self._sync_mirror(rarch)

    def _sync_mirror(self, arch):
        extra_args = "--exclude '*' --include '*.tar.gz'"
        if self.prerelease:
            s3_path = f"/pub/openshift-v4/{arch}/clients/operator-sdk/pre-release/"
        else:
            s3_path = f"/pub/openshift-v4/{arch}/clients/operator-sdk/{self.assembly}/"
        cmd = f"aws s3 sync --no-progress --exact-timestamps {extra_args} --delete ./{arch}/ s3://art-srv-enterprise{s3_path}"
        self.exec_cmd(cmd)
        if self.updatelatest:
            s3_path_latest = f"/pub/openshift-v4/{arch}/clients/operator-sdk/latest/"
            cmd = f"aws s3 sync --no-progress --exact-timestamps {extra_args} --delete ./{arch}/ s3://art-srv-enterprise{s3_path_latest}"
            self.exec_cmd(cmd)

    def exec_cmd(self, cmd):
        self._logger.info(f"running command: {cmd}")
        subprocess.run(cmd, shell=True, check=True)


@cli.command("operator-sdk-sync")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=False,
              help="The name of an assembly. e.g. 4.9.1")
@click.option("--nvr", metavar="BUILD_NVR", required=False,
              help="Pin specific Build NVR")
@click.option("--prerelease", metavar="PRE_RELEASE", is_flag=True, required=False,
              help="Use pre-release as directory name.")
@click.option("--updatelatest", metavar="UPDATE_LATEST_SYMLINK", is_flag=True, required=False,
              help="Update latest symlink on mirror")
@click.option("--force", metavar="FORCE", is_flag=True, required=False,
              help="Force update content on mirror")
@click.option("--arches", metavar="ARCHES", required=False,
              help="Arches in the build")
@pass_runtime
@click_coroutine
async def operator_sdk_sync(
        runtime: Runtime,
        group: str,
        assembly: str,
        nvr: str,
        prerelease: bool,
        updatelatest: bool,
        force: bool,
        arches: str):
    pipeline = OperatorSDKPipeline(
        runtime,
        group,
        assembly,
        nvr,
        prerelease,
        updatelatest,
        force,
        arches)
    await pipeline.run()
