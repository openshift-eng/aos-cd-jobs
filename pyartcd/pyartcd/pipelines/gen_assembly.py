import sys
import os
import click
import re
from pyartcd import exceptions, exectools
from pyartcd.github import GithubAPI, create_pr
from pyartcd.runtime import Runtime
from pyartcd.cli import cli, click_coroutine, pass_runtime
from ruamel.yaml import YAML
from io import StringIO

TOKEN = os.environ.get("GITHUB_TOKEN")
UPSTREAM_OWNER = "openshift"
OWNER = "openshift-art-build-bot"
REPO = "ocp-build-data"
GIT_AUTHOR = "AOS Automation Release Team"
GIT_EMAIL = "noreply@redhat.com"
RELEASE_CONFIG_FILE = "releases.yml"
DOOZER_OUTPUT_PATH = "doozer_output.txt"


def update_release_config(release_yml: str, data: str) -> str:
    """
    Function to update the release config with the new output from doozer
    :param release_yml: The yml file for the particular release currently in ocp-build-data
    :param data: The new data that we need to add to the releases.yml file of the specific release
    :return: The updated releases.yml file contents in string format
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    releases_config = yaml.load(release_yml)
    new_release_data = yaml.load(data)['releases']

    key = list(new_release_data.keys())[0]  # there is only one value in the list (key of the new release config)
    releases_config['releases'].update(new_release_data)
    releases_config['releases'].move_to_end(key, last=False)

    out = StringIO()
    yaml.dump(releases_config, out)
    return out.getvalue()


class GenPipeline:
    def __init__(self, runtime: Runtime, nightlies: str, custom: str, in_flight_prev: str, previous: str,
                 build_version: str, assembly_name: str):
        self.runtime = runtime
        self.nightlies = nightlies
        self.custom = custom
        self.in_flight_prev = in_flight_prev
        self.previous = previous
        self.build_version = build_version
        self.assembly_name = assembly_name
        self.build_number = self.runtime.get_job_run_name()

    async def run(self):
        # Create doozer cmd arguments
        nightly_args = ""
        for nightly in re.findall(r"([\w\-.]+)", self.nightlies):
            nightly_args += f" --nightly {nightly.strip()}"

        cmd = f"--group openshift-{self.build_version} release:gen-assembly --name {self.assembly_name} from-releases {nightly_args}"
        if self.custom:
            cmd += ' --custom'
            if (self.in_flight_prev and self.in_flight_prev != 'none') or self.previous:
                print("ERROR: Specifying IN_FLIGHT_PREV or PREVIOUS for a custom release is not allowed.")
                sys.exit(1)

        else:
            if self.in_flight_prev and self.in_flight_prev.lower() != 'none':
                cmd += f" --in-flight {self.in_flight_prev}"

            if self.previous and self.previous.lower() != 'none':
                for previous_data in re.findall(r"([\w\-.]+)", self.previous):
                    cmd += f" --previous {previous_data.strip()}"
            else:
                cmd += ' --auto-previous'

        # Run doozer command
        output_all = await exectools.cmd_gather_async(f"doozer --assembly=stream {cmd}")
        if output_all[0]:
            self.runtime.logger.error(f"Error: {output_all[2]}")
            self.runtime.logger.info(output_all[2])
            sys.exit(1)

        output = output_all[1]
        release_data = output[output.find("releases:"):].strip()

        self.runtime.logger.info(release_data)

        base = f"openshift-{self.build_version}"  # The base that we have to branch off of
        temp_branch = f"automation_{self.build_version}_{self.build_number}"  # format of the temporary branch

        # Create GitHub PR
        client = GithubAPI(
            owner=OWNER,
            repo=REPO,
            token=TOKEN
        )

        if client.branch_exists(branch=temp_branch):  # If a branch exists with the same name as temp_branch
            exceptions.GithubApiException(
                "Temporary branch already exists. Cannot push changes. Delete the temp branch and try again")

        # WARNING!!! This function will automatically sync your branch with upstream. Please take care if you are
        # trying to test! Please comment out the below function if you are testing.
        client.sync_with_upstream(branch=base)  # Sync the base branch with its upstream
        self.runtime.logger.info(f"Branch {base} synced with upstream")

        client.create_branch(base=base, new_branch_name=temp_branch)
        self.runtime.logger.info(f"Temporary branch {temp_branch} created")

        release_yml = client.get_file(branch=temp_branch, file_name=RELEASE_CONFIG_FILE)
        self.runtime.logger.info(f"Retrieved releases.yml from branch {temp_branch}")

        updated_config = update_release_config(release_yml, release_data)
        self.runtime.logger.info(f"Updated {RELEASE_CONFIG_FILE}")

        client.push_change(branch=temp_branch,
                           content=updated_config,
                           file_path=RELEASE_CONFIG_FILE,
                           commit_message=f"updated {RELEASE_CONFIG_FILE}",
                           git_author=GIT_AUTHOR,
                           git_email=GIT_EMAIL
                           )
        self.runtime.logger.info(f"Pushed changes from branch {temp_branch} to remote {base}")

        pr_url = create_pr(
            token=TOKEN,
            upstream_owner=UPSTREAM_OWNER,
            repo=REPO,
            title=f"Automated: Prepare release for {self.assembly_name}",
            body=f"Automated PR for gen-assembly {self.assembly_name}",
            head=f"{OWNER}:{temp_branch}",
            base=f"{base}"
        )
        self.runtime.logger.info(f"PR created successfully: {pr_url}")

        # Send back the doozer output and newly created URL so that it can be set in the build description
        temp_data = release_data.replace("\n", "<br>").replace(" ", "&nbsp;")
        temp_url = f"<a href={pr_url}> {pr_url} </a>"

        # It needs to be print here and not return as Jenkins will read from STDOUT
        print(
            "<u>Doozer output:</u><br>" + f"{temp_data}" + "<br><br>PR: " + f"{temp_url}"
        )

        # Send message to the corresponding release channel
        slack_client = self.runtime.new_slack_client()
        slack_client.bind_channel(f"{self.build_version}")
        await slack_client.say(
            f"Gen-assembly job for *{self.build_version}* successful. PR created: {pr_url}")


@cli.command("gen-assembly")
@click.option('--nightlies', required=True)
@click.option('--custom', required=False)
@click.option('--in-flight-prev', required=False)
@click.option('--previous', required=False)
@click.option('--build-version', required=True)
@click.option('--assembly-name', required=True)
@pass_runtime
@click_coroutine
async def gen_assembly_main(runtime, nightlies, custom, in_flight_prev, previous, build_version, assembly_name):
    pipeline = GenPipeline(runtime, nightlies=nightlies, custom=custom, in_flight_prev=in_flight_prev,
                           previous=previous, build_version=build_version, assembly_name=assembly_name)
    await pipeline.run()
