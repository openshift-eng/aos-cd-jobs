#!/usr/bin/python3

"""
query multi builds in union session and output limited result

usage:

./querybuilds.py -v 4.8 -t rhaos-4.7-rhel-8-candidate -i openshift-enterprise-deployer,ose-must-gather,ironic,cluster-etcd-operator
:return: 0
:return: 1
:output:
found the following embargoed build(s):
openshift-enterprise-deployer: 
  latest:   openshift-enterprise-deployer-container-v4.7.0-202104250659.p1
  previous: openshift-enterprise-deployer-container-v4.7.0-202104142050.p0
ironic:
  latest:   ironic-container-v4.7.0-202105072225.p1
  previous: ironic-container-v4.7.0-202105070851.p0

"""
import click
import koji
import wrapt
import sys

BREW_URL = "https://brewhub.engineering.redhat.com/brewhub"

class KojiWrapper(wrapt.ObjectProxy):
    """
    We've seen the koji client occasionally get
    Connection Reset by Peer errors.. "requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    Under the theory that these operations just need to be retried,
    this wrapper will automatically retry all invocations of koji APIs.
    """

    def __call__(self, *args, **kwargs):
        retries = 4
        while retries > 0:
            try:
                return self.__wrapped__(*args, **kwargs)
            except requests.exceptions.ConnectionError as ce:
                time.sleep(5)
                retries -= 1
                if retries == 0:
                    raise ce

@click.command()
@click.option('--images', '-i', default=None, type=str, help="provide image list, split with comma")
@click.option('--tag', '-t', default=None, type=str, help="provide image tag")
@click.option('--version', '-v', default=None, type=str, help="Please specify version")
def query_builds(images, tag, version):
    # :return: [output,message]
    # output would be formatted list if embargoed build found, else would be empty
    # message include some other alert message like no build found or build don't have expected tag

    koji_proxy = KojiWrapper(koji.ClientSession(BREW_URL, opts={'krbservice': 'brewhub', 'serverca': '/etc/pki/brew/legacy.crt'}))
    koji_proxy.gssapi_login()
    result = {}
    message = ''
    def checktag(build, image, tag):
        taglist = koji_proxy.listTags(build)
        if len(taglist) != 0:
            if tag not in [ i['name'] for i in taglist ]:
                return f'found {image} missing tag {tag} in build {build}\n'
        return ''

    for image in images.split(','):
        pattern = image + '-container-v' + version
        data = koji_proxy.search(pattern, 'build', 'regexp', {'limit': 2, 'order': '-id'})
        if len(data) != 2:
            # only one build found
            message += f'not enouth recent builds found for {image}\n'
            continue
        if data[0]['name'].endswith("p0") and data[1]['name'].endswith("p0"):
            # build become private
            result[image] = data
        # check all have correct tag
        message += checktag(data[0]['name'],image,tag)
        message += checktag(data[1]['name'],image,tag)

    if len(result) == 0 and len(message) == 0:
        sys.exit(0)
    if len(message) != 0:
        click.echo(message.strip('\n'))
    if len(result) != 0:
        output = 'found the following embargoed build(s):\n'
        for item in result.keys():
            output += f'{item}:\n'
            output += f'  latest:   {result[item][0]["name"]}\n'
            output += f'  previous: {result[item][1]["name"]}\n'
        click.echo(output.strip('\n'))
        sys.exit(1)    

if __name__ == '__main__':
    query_builds()
