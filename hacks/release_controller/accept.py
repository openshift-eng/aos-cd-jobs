#!/usr/bin/python3
import click
import os
import sys
import re
import requests
import subprocess
import functools
import semver


def sort_semver(versions):
    return sorted(versions, key=functools.cmp_to_key(semver.compare), reverse=True)


@click.command()
@click.option('-a', '--arch', default='amd64', help='Release architecture', type=click.Choice(['amd64',
              'arm64', 's390x', 'ppc64le']))
@click.option('-r', '--release', required=True, help='Release name (e.g. 4.3.13)')
@click.option("--reject", type=bool, is_flag=True, default=False, help='Reject instead of accept the release')
@click.option("--confirm", type=bool, is_flag=True, default=False,
              help="Must be specified to apply changes to server")
@click.option("--why", default=None, required=False, help='Reason to perform this action. required with --reject')
def run(arch, release, confirm, reject, why):

    """
    Verify that Passing upgrade tests exist force OpenShift release acceptance.
    Requires KUBECONFIG env var to be available

    \b
    Example invocation:
    $ ./accept.py -r 4.9.46 --confirm
    """
    if reject and not why:
        raise click.BadParameter('--why (a reason) is required when rejecting a release')

    kubeconfig = os.getenv('KUBECONFIG')
    if confirm and not kubeconfig:
        raise ValueError('Cannot find KUBECONFIG env')

    rc_url = f'https://{arch}.ocp.releases.ci.openshift.org/api/v1/releasestream/4-stable/release/{release}'
    release_info = requests.get(rc_url).json()
    release_phase_accepted = 'Accepted'
    if release_info['phase'] == release_phase_accepted:
        click.echo(f'Release is already {release_phase_accepted}. Nothing to do')
        sys.exit(0)

    upgrade_state_failed = 'Failed'
    upgrade_state_succeeded = 'Succeeded'

    major, minor = re.search(r'(\d+)\.(\d+).', release).groups()
    major, minor = int(major), int(minor)
    versions = [entry['From'] for entry in release_info['upgradesTo']]
    upgrade_version = sort_semver([x for x in versions if x.startswith(f'{major}.{minor}')])[0]
    upgrade_minor_version = sort_semver([x for x in versions if x.startswith(f'{major}.{minor-1}')])[0]

    upgrade_info, upgrade_minor_info = None, None
    for entry in release_info['upgradesTo']:
        if entry['From'] == upgrade_version:
            upgrade_info = entry
        if entry['From'] == upgrade_minor_version:
            upgrade_minor_info = entry

    upgrade_test = release_info['results']['blockingJobs']['upgrade']['state']
    if upgrade_test == upgrade_state_failed:
        if upgrade_info['Success'] > 0:
            for _, test in upgrade_info['History'].items():
                if test['state'] == upgrade_state_succeeded:
                    upgrade_url = test['url']
                    click.echo(f'Found passing upgrade test from {upgrade_version}: {upgrade_url}')
                    break
        else:
            raise ValueError(f'Could not find a successful upgrade test from {upgrade_version}')

    upgrade_minor_test = release_info['results']['blockingJobs']['upgrade-minor']['state']
    if upgrade_minor_test == upgrade_state_failed:
        if upgrade_minor_info['Success'] > 0:
            for _, test in upgrade_minor_info['History'].items():
                if test['state'] == upgrade_state_succeeded:
                    upgrade_minor_url = test['url']
                    click.echo(f'Found passing upgrade test from {upgrade_minor_version}: {upgrade_minor_url}')
                    break
        else:
            raise ValueError(f'Could not find a successful upgrade-minor test from {upgrade_minor_version}')

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

    if not confirm:
        click.echo(f"Would have run {cmd}")
        sys.exit(0)

    click.echo(f"Running command {cmd}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, universal_newlines=True)
    if result.returncode != 0:
        raise IOError(
            f"Command {cmd} returned {result.returncode}: stdout={result.stdout}, stderr={result.stderr}"
        )
    click.echo(result.stdout)


if __name__ == '__main__':
    run()
