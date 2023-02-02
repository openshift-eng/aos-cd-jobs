#!/usr/bin/python3
import click
import openshift as oc
import json
import time

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
def run(arch, release, upgrade_url, upgrade_minor_url, confirm, reject):

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

    with oc.api_server(api_url='https://api.ci.l2s4.p1.openshiftapps.com:6443'), oc.project(f'ocp{arch_suffix}'):
        update_imagestreamtag(arch_suffix, release, upgrade_url, upgrade_minor_url, confirm, reject)
        update_releasepayload(release, confirm, reject)

    exit(0)


def update_imagestreamtag(arch_suffix, release, upgrade_url, upgrade_minor_url, confirm, reject):
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
            annotations['release.openshift.io/phase'] = 'Accepted' if not reject else 'Rejected'

            verify_str = annotations['release.openshift.io/verify']
            verify = oc.Model(json.loads(verify_str))
            verify.upgrade.state = 'Succeeded' if not reject else 'Failed'
            if upgrade_url:
                verify.upgrade.url = upgrade_url
            verify['upgrade-minor'].state = 'Succeeded' if not reject else 'Failed'
            if upgrade_minor_url:
                verify['upgrade-minor'].url = upgrade_minor_url
            annotations['release.openshift.io/verify'] = json.dumps(verify._primitive(), indent=None)

        print(json.dumps(obj.model._primitive(), indent=4))
        if confirm:
            print('Attempting to apply this object.')
            return True
        else:
            print(WARNING + '--confirm was not specified. Run again to apply these changes.' + ENDC)
            return False

    if make_release_accepted(istag):
        istag.replace()
        print('Success!')
        print(f'Backup written to: {backup_filename}')


def update_releasepayload(release, confirm, reject):
    rp_qname = f'releasepayload/{release}'
    payload = oc.selector(rp_qname).object(ignore_not_found=True)
    if not payload:
        # TODO: Eventually, when ReleasePayloads are the source of truth, this should raise an exception...
        # raise IOError(f'Could not find {rp_qname}')
        print(WARNING + f'Warning: unable to find releasepayload "{release}"' + ENDC)
        return

    ts = int(round(time.time() * 1000))
    backup_filename = f'releasepayload_{release}.{ts}.json'
    if confirm:
        with open(backup_filename, mode='w+', encoding='utf-8') as backup:
            print(f'Creating backup file: {backup_filename}')
            backup.write(json.dumps(payload.model._primitive(), indent=4))

    def update_payload_override(obj):
        override = "Accepted"
        if reject:
            override = "Rejected"

        obj.model.spec.payloadOverride = {
            "override": override,
            "reason": f'Manually {override.lower()} by ART',
        }

        print(json.dumps(obj.model._primitive(), indent=4))
        if confirm:
            print('Attempting to apply this object.')
            return True
        else:
            print(WARNING + '--confirm was not specified. Run again to apply these changes.' + ENDC)
            return False

    if update_payload_override(payload):
        payload.replace()
        print('Success!')
        print(f'Backup written to: {backup_filename}')


if __name__ == '__main__':
    run()
