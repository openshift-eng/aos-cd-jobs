from pyartcd.cli import cli, pass_runtime
from pyartcd.runtime import Runtime
import openshift as oc
import click
import requests
import re
import base64
import json
import time
import sys
import subprocess
from subprocess import PIPE
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import List, Dict, Tuple


JENKINS_BASE_URL = "https://jenkins-rhcos.apps.ocp-virt.prod.psi.redhat.com"

# lifted verbatim from
# https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
DEFAULT_TIMEOUT = 5  # seconds


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class BuildRhcosPipeline:
    """Use the Jenkins API to query for existing builds and perhaps kick off a new one and wait for it."""
    def __init__(self, runtime: Runtime, new_build: bool, ignore_running: bool, version: str):
        self.runtime = runtime
        self.new_build = new_build
        self.ignore_running = ignore_running
        self.version = version
        self.api_token = None
        self._stream = None  # rhcos stream the version maps to
        self.dry_run = self.runtime.dry_run

        self.request_session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "POST"],
        )
        self.request_session.mount("https://", TimeoutHTTPAdapter(max_retries=retries))

    def run(self):
        self.request_session.headers.update({"Authorization": f"Bearer {self.retrieve_auth_token()}"})
        current = self.query_existing_builds()
        result = {}
        if current and not self.ignore_running:
            result["action"] = "skip"
            result["builds"] = [
                dict(url=b["url"], description=b["description"], result=None)
                for b in current
            ]
        else:
            # [lmeyer] there is a window of at least seconds after some other build is created,
            # when the above check cannot see it, and so this may start a new one. interestingly,
            # Jenkins seems to silently ignore identical builds in close succession (probably
            # double-click protection - if the parameters differ both are started), and should this
            # happen we will see a build start, assume we started it, and watch it to completion.
            # this seems unlikely to cause any problems other than mild confusion.
            self.start_build()
            if self.dry_run:
                print('DRY RUN - Exiting', file=sys.stderr)
            result["action"] = "build"
            result["builds"] = self.wait_for_builds()

        # final status in stdout
        print(json.dumps(result))

    def retrieve_auth_token(self) -> str:
        """Retrieve the auth token from the Jenkins service account to use with Jenkins API"""
        # https://github.com/coreos/fedora-coreos-pipeline/blob/main/HACKING.md#triggering-builds-remotely

        secret = None
        jenkins_uid = oc.selector('sa/jenkins').objects()[0].model.metadata.uid
        for s in oc.selector('secrets'):
            if s.model.type == "kubernetes.io/service-account-token" and s.model.metadata.annotations["kubernetes.io/service-account.name"] == "jenkins" and s.model.metadata.annotations["kubernetes.io/service-account.uid"] == jenkins_uid:
                secret_maybe = base64.b64decode(s.model.data.token).decode('utf-8')
                r = self.request_session.get(
                    f"{JENKINS_BASE_URL}/me/api/json",
                    headers={"Authorization": f"Bearer {secret_maybe}"},
                )
                if r.status_code == 200:
                    secret = secret_maybe
                    break

        if secret is None:
            raise Exception("Unable to find a valid Jenkins service account token")

        return secret

    @staticmethod
    def build_parameters(build: Dict[str, List[Dict]]) -> Dict:
        """Parse the build parameters from the build actions into a more usable dict"""
        parameters = next((  # first action that has parameters
            action["parameters"]
            for action in build["actions"]
            if "parameters" in action
        ), [])
        return {p["name"]: p["value"] for p in parameters}

    @staticmethod
    def build_url(job: str, number: int) -> str:
        return f"{JENKINS_BASE_URL}/job/{job}/{number}/"

    def query_existing_builds(self) -> List[Dict]:
        """Check if there are any existing builds for the given version. Returns builds in progress."""
        builds = []
        for job in ("build", "build-arch", "release"):
            builds.extend(
                dict(**b, job=job, parameters=self.build_parameters(b), url=self.build_url(job, b["number"]))
                for b in self.request_session.get(
                    f"{JENKINS_BASE_URL}/job/{job}/api/json?tree=builds[number,description,result,actions[parameters[name,value]]]",
                ).json()["builds"]
                if b["result"] is None  # build is still running when it has no status
            )

        return [b for b in builds if b["parameters"].get("STREAM") == self.stream]

    @property
    def stream(self):
        if self._stream:
            return self._stream

        # doozer --quiet -g openshift-4.14 config:read-group urls.rhcos_release_base.multi --default ''
        # https://releases-rhcos-art.apps.ocp-virt.prod.psi.redhat.com/storage/prod/streams/4.14-9.2/builds
        cmd = [
            "doozer",
            "--quiet",
            "--group", f'openshift-{self.version}',
            "config:read-group",
            "urls.rhcos_release_base.multi",
            "--default",
            "''"
        ]
        result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, check=False, universal_newlines=True)
        if result.returncode != 0:
            raise IOError(f"Command {cmd} returned {result.returncode}: stdout={result.stdout}, stderr={result.stderr}")
        match = re.search(r'streams/(.*)/builds', result.stdout)
        if match:
            self._stream = match[1]
        else:
            self._stream = self.version
        return self._stream

    def start_build(self):
        """Start a new build for the given version"""
        # determine parameters
        params = dict(STREAM=self.stream, EARLY_ARCH_JOBS="false")
        if self.new_build:
            params["FORCE"] = "true"
        job_url = f"{JENKINS_BASE_URL}/job/build/buildWithParameters"
        if self.dry_run:
            print(f"Would've started build at url={job_url} with params={params}", file=sys.stderr)
            return {}

        # start the build
        self.request_session.post(
            job_url,
            data=params,
        )

        # wait for a related build to begin
        initial_builds = []
        for _ in range(300):
            if initial_builds:
                break
            time.sleep(1)  # may take a few seconds for the build to start
            initial_builds = self.query_existing_builds()
        else:  # only gets here if the for loop reaches the count
            raise Exception("Waited too long for build to start")

        return initial_builds

    def build_result(self, job, number):
        """Query the status of a known build"""
        return next((  # expecting exactly one result
            dict(
                url=self.build_url(job, b["number"]),
                description=b["description"] or "[no description yet]",
                result=b["result"],
            ) for b in self.request_session.get(
                f"{JENKINS_BASE_URL}/job/{job}/api/json?tree=builds[number,description,result]"
            ).json()["builds"]
            if b["number"] == number
        ), None)

    def wait_for_builds(self):
        """Wait for all builds for this version to complete, and give status updates on stderr"""
        builds_seen: Dict[Tuple, str] = {}
        completed_builds: Dict[Tuple, Dict] = {}
        for _ in range(1440):  # x 10s = about 4 hours (slower if bad/no response)
            new_builds_seen: Dict[Tuple, str] = {
                (b["job"], b["number"]): b["description"] or "[no description yet]"
                for b in self.query_existing_builds()
            }

            # check if any previous builds have newly completed
            for spec in builds_seen.keys():
                if spec not in new_builds_seen and spec not in completed_builds:
                    completed_builds[spec] = completed = self.build_result(*spec)
                    if completed:  # silently ignore if it's somehow not there... should never happen
                        print(f"{completed['url']} finished with {completed['result']}: '{completed['description']}'", file=sys.stderr)

            # if there are no builds left running, we're done
            if not new_builds_seen:
                break

            # check if there are new or changed builds
            for spec, description in new_builds_seen.items():
                job, number = spec
                if spec not in builds_seen:
                    print(f"New build #{number} of {job} job: {self.build_url(job, number)}", file=sys.stderr)
                elif description != builds_seen[spec]:
                    print(f"Build #{number} of {job} job update: '{description}'", file=sys.stderr)

            builds_seen = new_builds_seen
            time.sleep(10)
        else:  # only gets here if the for loop reaches the count
            raise Exception("Waited too long for builds to complete")

        return list(completed_builds.values())


@cli.command("build-rhcos")
@click.option("--version", required=True, type=str,
              help="The version to build, e.g. '4.13'")
@click.option("--ignore-running", required=False, default=False, type=bool,
              help="Ignore in-progress builds instead of just exiting like usual")
@click.option("--new-build", required=False, default=False, type=bool,
              help="Force a new build even if no changes were detected from the last build")
@pass_runtime
def build_rhcos(runtime: Runtime, new_build: bool, ignore_running: bool, version: str):
    if not re.match(r'^\d+\.\d+$', version):
        raise Exception("Version must be in the format 'x.y'")
    BuildRhcosPipeline(runtime, new_build, ignore_running, version).run()
