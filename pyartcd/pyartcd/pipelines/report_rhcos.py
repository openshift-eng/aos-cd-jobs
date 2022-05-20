from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime

import click
import asyncio
from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import NoBuildData
from subprocess import run


VERSIONS = [
    "4.6",
    "4.7",
    "4.8",
    "4.9",
    "4.10",
    "4.11",
    "4.12"
]

ARCHES = [
    "amd64",
    "s390x",
    "ppc64le",
    "arm64"
]

RHCOS_URLS = {
    'amd64': 'https://jenkins-rhcos-art.cloud.privileged.psi.redhat.com',
    's390x': 'https://jenkins-rhcos.cloud.s390x.psi.redhat.com',
    'ppc64le': 'https://jenkins-rhcos.cloud.p8.psi.redhat.com',
    'arm64': 'https://jenkins-rhcos.cloud.arm.psi.redhat.com'
}


class CheckRhcosPipeline:
    def __init__(self, runtime: Runtime, channel: str):
        self.runtime = runtime
        self.channel = channel
        self.result = dict()

    async def get_data(self):
        futures = []
        for arch in ARCHES:
            futures.append(self.get_data_for_arch(arch))
        answers = await asyncio.gather(*futures)

        for arch, answer in zip(ARCHES, answers):
            self.result[arch] = answer


    async def get_data_for_arch(self, arch):
        jenkins = Jenkins(RHCOS_URLS[arch])
        print(f"Checking {arch}")

        a = dict()
        for version in VERSIONS:
            if arch == 'arm64' and int(version.split('.')[-1]) < 9:
                # arm64 was introduced in 4.9
                continue
            try:
                project = [p for p in jenkins.keys() if p.endswith(f'-{version}')][0]
            except IndexError:
                continue
            pipeline = jenkins[project]

            try:
                complete_id = pipeline.get_last_completed_buildnumber()
            except NoBuildData:
                complete_id = -1
                bad_id = 0
                good_id = 0
            try:
                good_id = pipeline.get_last_good_buildnumber()
            except NoBuildData:
                good_id = -1
            try:
                bad_id = pipeline.get_last_failed_buildnumber()
            except NoBuildData:
                bad_id = -1

            if complete_id == good_id:
                r = 'good'
            elif complete_id == bad_id:
                r = f'bad (since {bad_id - good_id} attempts)'
            else:
                r = 'No results'
            a[version] = r
        print(f"Done checking {arch}")
        return a

    def present_data(self):
        version_result = {}
        for version in VERSIONS:
            version_result[version] = {}
            for arch in ARCHES:
                r = self.result[arch].get(version, None)
                version_result[version][arch] = r
        print(version_result)

        output = """
        digraph {
          node [ shape=none fontname=Helvetica ]
          n [ label = <
            <table>
              <tr>
        """

        header = "<td></td>"
        for arch in ARCHES:
            header = f'{header}\n<td>{arch}</td>'

        output = f'{output}\n{header}\n</tr>'

        for version in VERSIONS:
            output = f"{output}\n<tr><td>{version}</td>"
            for arch in ARCHES:
                result = version_result[version][arch]
                if result == 'good':
                    color = "green"
                elif not result:
                    color = 'white'
                else:
                    color = 'red'
                cell = f'<td bgcolor="{color}">{result}</td>'
                output = f'{output}\n{cell}'
            output = f'{output}\n</tr>'

        output = f'{output}\n</table>\n> ]\n}}'
        return output


@cli.command('check-rhcos')
@click.option('--file-name', required=False, default='rhcos_result.png',
              help='File name image')
@click.option('--slack-channel', required=False, default=None,
              help='Slack channel to post result to')
@pass_runtime
@click_coroutine
async def check_rhcos(runtime: Runtime, slack_channel: str, file_name: str):
    rhcos_checker = CheckRhcosPipeline(runtime, slack_channel)
    await rhcos_checker.get_data()
    dot = rhcos_checker.present_data()
    run(['dot', '-Tpng', f'-o{file_name}'], input=dot.encode())
    if slack_channel:
        slack_client = runtime.new_slack_client()
        slack_client.bind_channel(slack_channel)
        await slack_client.post_image('rhcos build result', file_name)
