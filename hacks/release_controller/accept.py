#!/usr/bin/python3
import click
import os
import sys
import openshift as oc
import json
import re
import requests
import subprocess

WARNING = '\033[91m'
ENDC = '\033[0m'


@click.command()
@click.option('-a', '--arch', default='amd64', help='Release architecture', type=click.Choice(['amd64',
'arm64','s390x','ppc64le']))
@click.option('-r', '--release', required=True, help='Release name (e.g. 4.3.13)')
@click.option('-u', '--upgrade-url', default=None, required=False, help='URL to successful upgrade job')
@click.option('-m', '--upgrade-minor-url', default=None, required=False, help='URL to successful upgrade-minor job')
@click.option("--reject", type=bool, is_flag=True, default=False, help='Reject instead of accept the release')
@click.option("--confirm", type=bool, is_flag=True, default=False,
              help="Must be specified to apply changes to server")
@click.option("--why", default=None, required=False, help='Reason to perform this action. required with --reject')
@click.option("--allow-upgrade-to-change", type=bool, is_flag=True, default=False, help='Allow when new upgrade-to version is different from old upgrade-to')
def run(arch, release, upgrade_url, upgrade_minor_url, confirm, reject, why, allow_upgrade_to_change):

    """
    Sets annotations to force OpenShift release acceptance.
    Requires https://github.com/openshift/openshift-client-python to be setup in your PYTHONPATH.

    \b
    Add github user to this group to enable them: https://github.com/openshift/release/pull/15827

    \b
    If openshift-client-python is in $HOME/projects/openshift-client-python:
    $ export PYTHONPATH=$PYTHONPATH:$HOME/projects/openshift-client-python/packages

    \b
    Example invocation:
    $ ./accept.py -r 4.4.0-rc.3
                  -u 'https://prow.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/575'
                  -m 'https://prow.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/461'
                  --confirm
    """

    if not upgrade_minor_url and not upgrade_url:
        click.echo('One or both upgrade urls must be specified in order to accept the release')
        sys.exit(1)

    if reject and not why:
        click.echo('--why (a reason) is required when rejecting a release')
        sys.exit(1)

    kubeconfig = os.getenv('KUBECONFIG')
    if not kubeconfig:
        click.echo('cannot find KUBECONFIG env')
        sys.exit(1)

    release_phase_rejected = 'Rejected'
    upgrade_state_failed = 'Failed'

    rc_url = f'https://{arch}.ocp.releases.ci.openshift.org/api/v1/releasestream/4-stable/release/{release}'
    release_info = requests.get(rc_url).json()
    if release_info['phase'] != release_phase_rejected:
        click.echo(f'release is not {release_phase_rejected}. aborting')
        sys.exit(1)
    
    if upgrade_url:
        old_test = release_info['blockingJobs']['upgrade']
        if old_test['state'] != upgrade_state_failed:
            click.echo(f'existing upgrade test is not {upgrade_state_failed}. aborting')
            sys.exit(1)
        assert_upgrade_test_state(release, arch, old_test['url'], upgrade_url, allow_upgrade_to_change)

    if upgrade_minor_url:
        old_test = release_info['blockingJobs']['upgrade-minor']
        if old_test['state'] != upgrade_state_failed:
            click.echo(f'existing upgrade test is not {upgrade_state_failed}. aborting')
            sys.exit(1)
        assert_upgrade_test_state(release, arch, old_test['url'], upgrade_minor_url, allow_upgrade_to_change)

    accept_script_name = 'release-tool.py'
    accept_script_url = f'https://raw.githubusercontent.com/openshift/release-controller/master/hack/{accept_script_name}'

    response = requests.get(accept_script_url)
    with open(accept_script_name, 'w') as f:
        f.write(response.text)

    action = 'reject' if reject else 'accept'
    message = f'Manually {action}ed by ART'

    if reject or why:
        reason = why
    else:
        reason = 'Accepting a release on the basis a successful upgrade test'

    cmd = [
        'python3', accept_script_name,
        '--arch', arch,
        '--message', message,
        '--reason', reason,
        '--context', 'app.ci',
        '--kubeconfig', kubeconfig,
        '--imagestream', 'release'
    ]
    if confirm:
        cmd += '--execute'
    
    cmd.extend([
        action,
        release
    ])

    print(f"Running command {cmd}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, universal_newlines=True)
    if result.returncode != 0:
        raise IOError(
            f"Command {cmd} returned {result.returncode}: stdout={result.stdout}, stderr={result.stderr}"
        )
    print(result.stdout)


def assert_upgrade_test_state(release_name, arch, old_prowjob_url, new_prowjob_url, allow_upgrade_to_change=False):
    prowjob_success = 'success'
    prowjob_fail = 'failure'
    prow_host = 'https://prow.ci.openshift.org'
    gcs_host = 'https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com'
    subdir = 'origin-ci-test/logs'
    prow_pattern = rf'{prow_host}/view/gs/{subdir}/(.*)/(\d+)'

    def get_prowjob(prowjob_url):
        z = re.match(prow_pattern, prowjob_url)
        if not z or len(z.groups()) != 2:
            raise ValueError(f"given url [{prowjob_url}] doesn't match pattern [{prow_pattern}]")
        test_name, test_id = z.groups()
        gcs_bucket_url = f'{gcs_host}/gcs/{subdir}/{test_name}/{test_id}/prowjob.json'
        r = requests.get(gcs_bucket_url)
        prowjob = oc.Model(r.json())
        return prowjob

    # make sure existing test has failed
    old_prowjob = get_prowjob(old_prowjob_url)
    old_upgrade_to = old_prowjob.metadata.annotations["release.openshift.io/from-tag"]
    if old_prowjob.status.state != prowjob_fail:
        raise ValueError(f'existing prowjob {old_prowjob_url} test has state={old_prowjob.status.state} and not {prowjob_fail}')

    # make sure new test has passed
    new_prowjob = get_prowjob(new_prowjob_url)
    if new_prowjob.status.state != prowjob_success:
        raise ValueError(f'new prowjob {new_prowjob_url} test has state={new_prowjob.status.state} and not {prowjob_success}')

    # make sure new test release tag is same as the given release
    new_release = new_prowjob.metadata.annotations["release.openshift.io/tag"]
    if new_release != release_name:
        raise ValueError(f'new prowjob {new_prowjob_url} test has release tag={new_release} and not {release_name}')

    # make sure new test upgrade_to is same as old test upgrade_to
    new_upgrade_to = new_prowjob.metadata.annotations["release.openshift.io/from-tag"]
    if new_upgrade_to != old_upgrade_to:
        if allow_upgrade_to_change:
            print('new prowjob upgrade_to_version is different from old prowjob. --allow-upgrade-to-change is in effect so progressing..')
        else:
            raise ValueError(f'new prowjob {new_prowjob_url} has upgrade_to={new_upgrade_to} and not {old_upgrade_to}. To override pass --allow-upgrade-to-change')


if __name__ == '__main__':
    run()
