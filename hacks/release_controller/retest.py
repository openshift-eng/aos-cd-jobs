#!/usr/bin/python3
import click
import openshift as oc
import json
import time
import pprint

WARNING = '\033[91m'
ENDC = '\033[0m'


@click.command()
@click.option('-a', '--arch', default='amd64', help='Release architecture (amd64, s390x, ppc64le)')
@click.option('-r', '--release', required=True, help='Release name (e.g. 4.3.13)')
@click.option("--confirm", type=bool, is_flag=True, default=False,
              help="Must be specified to apply changes to server")
def run(arch, release, confirm):

    """
    Sets annotations and deletes prowjobs to restart testing on a release.
    requires:  pip3 install openshift-client
    OR https://github.com/openshift/openshift-client-python must be setup in your PYTHONPATH.

    \b
    If openshift-client-python is in $HOME/projects/openshift-client-python:
    $ export PYTHONPATH=$PYTHONPATH:$HOME/projects/openshift-client-python/packages

    \b
    Example invocation:
    $ ./retest.py -r 4.4.0-rc.3
                  --confirm
    """

    arch_suffix = ''
    if arch != 'amd64' and arch != 'x86_64':
        arch_suffix = f'-{arch}'

    t1 = input('Enter a token for https://api.ci.l2s4.p1.openshiftapps.com: ')

    with oc.api_server(api_url='https://api.ci.l2s4.p1.openshiftapps.com:6443'), oc.options({'as': 'system:admin'}), oc.token(t1):
        with oc.project('ci'):
            print(f'Searching for prowjobs associated with {release}')
            prowjobs = oc.selector('prowjobs').narrow(lambda obj: obj.model.metadata.annotations['release.openshift.io/tag'] == release and 'chat-bot' not in obj.model.metadata.name )
            print(f'Found prowjobs: {prowjobs.qnames()}')
            if confirm:
                print('Deleting associated prowjobs')
                prowjobs.delete()
            else:
                print(WARNING + 'Run with --confirm to delete these resources' + ENDC)

    with oc.api_server(api_url='https://api.ci.openshift.org'), oc.options({'as': 'system:admin'}):
        with oc.project(f'ocp{arch_suffix}'):

            istag_qname = f'istag/release{arch_suffix}:{release}'
            istag = oc.selector(istag_qname).object(ignore_not_found=True)
            if not istag:
                raise IOError(f'Could not find {istag_qname}')

            def trigger_retest(obj):
                for annotations in (obj.model.image.metadata.annotations, obj.model.metadata.annotations, obj.model.tag.annotations):
                    annotations.pop('release.openshift.io/message', None)
                    annotations.pop('release.openshift.io/phase', None)
                    annotations.pop('release.openshift.io/reason', None)
                    annotations.pop('release.openshift.io/verify', None)

                print(json.dumps(obj.model._primitive(), indent=4))
                if confirm:
                    print('Attempting to apply this object.')
                    return True
                else:
                    print(WARNING + '--confirm was not specified. Run again to apply these changes.' + ENDC)
                    exit(0)

            result, changed = istag.modify_and_apply(trigger_retest, retries=10)
            if not changed:
                print(WARNING + 'No change was applied to the object' + ENDC)
                print(f'Details:\n{result.as_json()}')
                exit(1)

        print('Success!')


if __name__ == '__main__':
    run()
