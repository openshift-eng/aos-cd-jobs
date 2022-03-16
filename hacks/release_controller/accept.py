#!/usr/bin/python3
import click
import openshift as oc
import json
import time
import re
import requests

WARNING = '\033[91m'
ENDC = '\033[0m'


@click.command()
@click.option('-a', '--arch', default='amd64', help='Release architecture (amd64, s390x, ppc64le)')
@click.option('-r', '--release', required=True, help='Release name (e.g. 4.3.13)')
@click.option('-u', '--upgrade-url', default=None, required=False, help='URL to successful upgrade job')
@click.option('-m', '--upgrade-minor-url', default=None, required=False, help='URL to successful upgrade-minor job')
@click.option("--reject", type=bool, is_flag=True, default=False, help='Reject instead of accept the release')
@click.option("--confirm", type=bool, is_flag=True, default=False,
              help="Must be specified to apply changes to server")
@click.option("--allow-upgrade-to-change", type=bool, is_flag=True, default=False, help='Allow when new upgrade-to version is different from old upgrade-to')
def run(arch, release, upgrade_url, upgrade_minor_url, confirm, reject, allow_upgrade_to_change):

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
                  -u 'https://prow.svc.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/575'
                  -m 'https://prow.svc.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/461'
                  --confirm
    """

    if not upgrade_minor_url and not upgrade_url:
        click.echo('One or both upgrade urls must be specified in order to accept the release')
        exit(1)

    arch_suffix = ''
    if arch != 'amd64' and arch != 'x86_64':
        arch_suffix = f'-{arch}'

    phase_rejected = 'Rejected'
    phase_accepted = 'Accepted'
    upgrade_state_success = 'Succeeded'
    upgrade_state_failed = 'Failed'

    # store upgrade test state in dict: url -> state
    prowjobs = {}

    prow_host = 'https://prow.ci.openshift.org'
    gcs_host = 'https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com'
    subdir = 'origin-ci-test/logs'
    prow_pattern = rf'{prow_host}/view/gs/{subdir}/(.*)/(\d+)'

    def assert_upgrade_test_state(release_name, arch, old_prowjob_url, new_prowjob_url, allow_upgrade_to_change=False):
        prowjob_success = 'success'
        prowjob_fail = 'failure'

        def get_prowjob(prowjob_url):
            if prowjob_url in prowjobs:
                return prowjobs[prowjob_url]
            z = re.match(prow_pattern, prowjob_url)
            if not z or len(z.groups()) != 2:
                raise ValueError(f"given url [{prowjob_url}] doesn't match pattern [{prow_pattern}]")
            test_name, test_id = z.groups()
            gcs_bucket_url = f'{gcs_host}/gcs/{subdir}/{test_name}/{test_id}/prowjob.json'
            r = requests.get(gcs_bucket_url)
            prowjob = oc.Model(r.json())
            prowjobs[prowjob_url] = prowjob
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

        # make sure new test arch is same
        new_arch = new_prowjob.metadata.annotations["release.openshift.io/architecture"]
        if new_arch != arch:
            raise ValueError(f'new prowjob {new_prowjob_url} test has arch={new_arch} and not {arch}')

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

    with oc.api_server(api_url='https://api.ci.l2s4.p1.openshiftapps.com:6443'), \
         oc.project(f'ocp{arch_suffix}'):

        istag_qname = f'istag/release{arch_suffix}:{release}'
        istag = oc.selector(istag_qname).object(ignore_not_found=True)
        if not istag:
            raise IOError(f'Could not find {istag_qname}')

        ts = int(round(time.time() * 1000))
        backup_filename = f'release{arch_suffix}_{release}.{ts}.json'
        if confirm:
            with open(backup_filename, mode='w+', encoding='utf-8') as backup:
                print(f'Creating backup file: {backup_filename}')
                backup.write(json.dumps(istag.model._primitive(), indent=4))

        def make_release_accepted(obj):
            for annotations in (obj.model.image.metadata.annotations, obj.model.metadata.annotations, obj.model.tag.annotations):
                annotations.pop('release.openshift.io/message', None)
                annotations.pop('release.openshift.io/reason', None)
                phase = annotations['release.openshift.io/phase']
                if phase != phase_rejected:
                    raise ValueError(f'Release is phase={phase} and not {phase_rejected}. Aborting')
                annotations['release.openshift.io/phase'] = phase_accepted if not reject else phase_rejected

                verify_str = annotations['release.openshift.io/verify']
                verify = oc.Model(json.loads(verify_str))

                if upgrade_url:
                    assert_upgrade_test_state(release, arch, verify.upgrade.url, upgrade_url, allow_upgrade_to_change)
                    verify.upgrade.state = upgrade_state_success if not reject else upgrade_state_failed
                    verify.upgrade.url = upgrade_url

                if upgrade_minor_url:
                    upgrade_minor = 'upgrade-minor'
                    assert_upgrade_test_state(release, arch, verify[upgrade_minor].url, upgrade_minor_url, allow_upgrade_to_change)
                    verify[upgrade_minor].url = upgrade_minor_url
                    verify[upgrade_minor].state = upgrade_state_success if not reject else upgrade_state_failed

                annotations['release.openshift.io/verify'] = json.dumps(verify._primitive(), indent=None)

            print(json.dumps(obj.model._primitive(), indent=4))
            if confirm:
                print('Attempting to apply this object.')
                return True
            else:
                print(WARNING + '--confirm was not specified. Run again to apply these changes.' + ENDC)
                exit(0)

        make_release_accepted(istag)
        istag.replace()
        print('Success!')
        print(f'Backup written to: {backup_filename}')


if __name__ == '__main__':
    run()
