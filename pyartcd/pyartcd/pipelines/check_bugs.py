import asyncio
import subprocess
import concurrent
import sys
import click
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry

from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime

BASE_URL = 'https://api.openshift.com/api/upgrades_info/v1/graph?arch=amd64&channel=fast'
ELLIOTT_BIN = 'elliott'


def get_next_version(version: str) -> str:
    major, minor = version.split('.')[:2]
    return '.'.join([major, str(int(minor) + 1)])


class CheckBugsPipeline:
    def __init__(self, runtime: Runtime, channel: str, versions: list, pre_releases: list) -> None:
        self.runtime = runtime
        self.versions = versions
        self.pre_releases = pre_releases
        self.logger = runtime.logger
        self.applicable_versions = []
        self.blockers = {}
        self.regressions = {}
        self.slack_client = None if not channel else self.initialize_slack_client(runtime, channel)
        self.unstable = False  # This is set to True if any of the commands in the pipeline fail

    @staticmethod
    def initialize_slack_client(runtime: Runtime, channel: str):
        if not channel.startswith('#'):
            raise ValueError('Invalid Slack channel name provided')

        slack_client = runtime.new_slack_client()
        slack_client.bind_channel(channel)
        return slack_client

    async def run(self):
        # Check applicable OCP versions
        await self._check_applicable_versions()

        # Find blocker bugs
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for v in self.applicable_versions:
                futures.append(executor.submit(self._find_blockers, v))
            for f in futures:
                try:
                    self.blockers.update(f.result())
                except TypeError:
                    # In case no blockers have been found
                    pass

        # Find regressions
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for v in self.applicable_versions:
                futures.append(executor.submit(self._find_regressions, v))
            for f in futures:
                try:
                    self.regressions.update(f.result())
                except TypeError:
                    # In case no regressions have been found
                    pass

        # Notify Slack
        await self._slack_report()
        sys.exit(1 if self.unstable else 0)

    async def _check_applicable_versions(self):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for v in self.versions:
                tasks.append(asyncio.ensure_future(self.is_ga(v, session)))
            responses = await asyncio.gather(*tasks)
            ga_info = dict(zip(self.versions, responses))

        self.applicable_versions = [v for v in self.versions if ga_info.get(v, True)]

        if self.applicable_versions:
            self.logger.info(f'Found applicable versions: {" ".join(self.applicable_versions)}')
        else:
            self.logger.warning('No applicable versions found')

    async def is_ga(self, version: str, session):
        # 3.11 is an exception, no need to query Openshift API
        if version == '3.11':
            return True

        url = f'{BASE_URL}-{version}'

        # A release is considered GA'd if nodes are found
        retry_options = ExponentialRetry(attempts=10)
        retry_client = RetryClient(client_session=session, retry_options=retry_options)
        async with retry_client.get(url, headers={'Accept': 'application/json'}) as response:
            if response.status != 200:
                self.logger.error('Received status %s for URL %s', response.status, url)
                raise RuntimeError

            response_body = await response.json()
            nodes = response_body['nodes']
            return len(nodes) > 0

    def _find_blockers(self, version: str):
        self.logger.info(f'Checking blocker bugs for Openshift {version}')

        cmd = [
            ELLIOTT_BIN,
            f'--group=openshift-{version}',
            f'--working-dir={version}-working',
            'find-bugs:blocker',
            '--output=slack'
        ]
        self.logger.info(f'Executing command: {" ".join(cmd)}')

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if out:
            self.logger.info(out.decode())
        errcode = process.returncode
        if errcode:
            self.unstable = True
            self.logger.error(f'Command failed: cmd={cmd} status={errcode}. Output: {err.decode()}')
            return None

        out = out.decode().strip().splitlines()
        if not out:
            self.logger.info('No blockers found for version %s', version)
            return None
        self.logger.info('Cmd returned: %s', out)
        return {version: out}

    def _find_regressions(self, version: str):
        # Do nothing for 3.11
        if version == '3.11':
            return None

        # Check pre-release
        if self._next_is_prerelease(version):
            self.logger.info(
                'Version %s is in pre-release state: skipping regression checks for %s',
                get_next_version(version), version
            )
            return None

        self.logger.info(f'Checking possible regressions for Openshift {version}')

        # Verify bugs
        cmd = [
            ELLIOTT_BIN,
            f'--group=openshift-{version}',
            '--assembly=stream',
            f'--working-dir={version}-working',
            'verify-bugs',
            '--output=slack'
        ]
        self.logger.info(f'Executing command: {" ".join(cmd)}')

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if out:
            self.logger.info(out.decode())

        errcode = process.returncode
        res = None

        # If returncode is 0 then no regressions were found
        if not errcode:
            self.logger.info('No regressions found for version %s', version)
            return res

        out = out.decode().strip().splitlines()
        if out:
            res = {version: out}
        else:
            self.unstable = True
            self.logger.error(f'Command failed: cmd={cmd} status={errcode}. Output: {err.decode()}')
        return res

    def _next_is_prerelease(self, version: str) -> bool:
        return get_next_version(version) in self.pre_releases

    async def _slack_report(self):
        # If no issues have been found, do nothing
        if not any((self.blockers, self.regressions)) or not self.slack_client:
            return

        # Merge results
        from collections import defaultdict
        report = defaultdict(list)
        for d in (self.blockers, self.regressions):
            for k, v in d.items():
                report[k].extend(v)

        # Format output message
        message = ':red-siren: *There are some issues to look into:*'
        for k in report.keys():
            message += f'\n:warning:*{k}*'
            for i in report[k]:
                message += f'\n{i}'

        self.logger.info('Sending notification to Slack')
        self.logger.debug(message)
        await self.slack_client.say(message)


@cli.command('check-bugs')
@click.option('--slack_channel', required=False,
              help='Slack channel to be notified for failures')
@click.option('--version', required=True, multiple=True,
              help='OCP version to check for blockers e.g. 4.7')
@click.option('--pre_release', required=False, multiple=True,
              help='OCP versions still in pre-release state')
@pass_runtime
@click_coroutine
async def check_bugs(runtime: Runtime, slack_channel: str, version: list, pre_release: list):
    pipeline = CheckBugsPipeline(runtime, channel=slack_channel, versions=version, pre_releases=pre_release)
    await pipeline.run()
