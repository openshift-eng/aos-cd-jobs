#!/usr/bin/env python2
import base64
import json
import logging
import ssl
import subprocess
import sys
import threading

import click
import requests
from rhmsg.activemq.producer import AMQProducer
from rhmsg.activemq.consumer import AMQConsumer


# Expose errors during signing for debugging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

######################################################################
URLS = {
    'dev': (
        'amqps://messaging-devops-broker01.dev1.ext.devlab.redhat.com:5671',
        'amqps://messaging-devops-broker02.dev1.ext.devlab.redhat.com:5671',
        'amqps://messaging-devops-broker03.dev1.ext.devlab.redhat.com:5671',
        'amqps://messaging-devops-broker04.dev1.ext.devlab.redhat.com:5671',
    ),
    'qa': (
        'amqps://messaging-devops-broker01.web.qa.ext.phx1.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.qa.ext.phx1.redhat.com:5671',
        'amqps://messaging-devops-broker03.web.qa.ext.phx1.redhat.com:5671',
        'amqps://messaging-devops-broker04.web.qa.ext.phx1.redhat.com:5671',
    ),
    'stage': (
        'amqps://messaging-devops-broker01.web.stage.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.stage.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker03.web.stage.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker04.web.stage.ext.phx2.redhat.com:5671',
    ),
    'prod': (
        'amqps://messaging-devops-broker01.web.prod.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.prod.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker03.web.prod.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker04.web.prod.ext.phx2.redhat.com:5671',
    ),

}

TOPIC = 'VirtualTopic.eng.art.artifact.sign'

# TODO: In the future we need to handle 'rhcos' having '4.1'
# hard-coded into the URL path.
MESSAGE_DIGESTS = {
    'openshift': 'https://mirror.openshift.com/pub/openshift-v4/{arch}/clients/{release_stage}/{release_name}/sha256sum.txt',
    'rhcos': 'https://mirror.openshift.com/pub/openshift-v4/{arch}/dependencies/rhcos/{release_name_xy}/{release_name}/sha256sum.txt'
}
DEFAULT_CA_CHAIN = "/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt"

# This is the JSON we send OVER the bus when requesting signatures
SIGN_REQUEST_MESSAGE_FIELDS = [
    "artifact",
    # Added by ART
    "artifact_meta",
    "request_id",
    "requestor",
    "sig_keyname",
]

ART_CONSUMER = 'Consumer.openshift-art-signatory.{env}.VirtualTopic.eng.robosignatory.art.sign'


def get_release_tag(release_name, arch):
    """Determine the quay destination tag where a release image lives, based on the
    release name and arch (since we can now have multiple arches for each release name)
    - make sure it includes the arch in the tag to distinguish from any other releases of same name.

    e.g.:
    (4.2.0-0.nightly-s390x-2019-12-10-202536, s390x) remains 4.2.0-0.nightly-s390x-2019-12-10-202536
    (4.3.0-0.nightly-2019-12-07-121211, x86_64) becomes 4.3.0-0.nightly-2019-12-07-121211-x86_64
    (4.9.0-0.nightly-arm64-2021-06-07-121211, aarch64) remains 4.9.0-0.nightly-arm64-2021-06-07-121211
    """
    go_arch_for = dict(aarch64="arm64", s390x="s390x", ppc64le="ppc64le", x86_64="amd64")
    return release_name if go_arch_for[arch] in release_name else "{}-{}".format(release_name, arch)


######################################################################
# Click stuff! Define these here and reuse them later because having
# 'required' options in the global context creates a poor user
# experience. Running "this-script <sub-command> --help" won't work
# until every global required option is provided.
context_settings = dict(help_option_names=['-h', '--help'])
requestor = click.option("--requestor", required=True, metavar="USERID",
                         help="The user who requested the signature")
product = click.option("--product", required=True,
                       type=click.Choice(["openshift", "rhcos"]),
                       help="Which product this signature is for")
request_id = click.option("--request-id", required=True, metavar="BUILDURL",
                          help="Unique build job identifier for this signing request, "
                          "use the job URL from Jenkins: $env.BUILD_URL")
sig_keyname = click.option("--sig-keyname", required=True,
                           type=click.Choice(['test', 'redhatrelease2', 'beta2']),
                           help="Name of the key to have sign our request")
release_name_opt = click.option("--release-name", required=True, metavar="SEMVER",
                            help="Numerical name of this release, for example: 4.1.0-rc.10")
arch_opt = click.option("--arch", required=True, metavar="ARCHITECTURE",
                   type=click.Choice(['x86_64', 'ppc64le', 's390x', 'aarch64']),
                   help="Which architecture this release was built for")
client_type = click.option("--client-type", required=True, metavar="VAL",
                   type=click.Choice(['ocp', 'ocp-dev-preview']),
                   help="What type of client needs to be signed")
client_cert = click.option("--client-cert", required=True, metavar="CERT-PATH",
                           type=click.Path(exists=True),
                           help="Path to the client certificate for UMB authentication")
client_key = click.option("--client-key", required=True, metavar="KEY-PATH",
                          type=click.Path(exists=True),
                          help="Path to the client key for UMB authentication")
env = click.option("--env", required=False, metavar="ENVIRONMENT",
                   default='stage',
                   type=click.Choice(['dev', 'stage', 'prod']),
                   help="Which UMB environment to send to")
noop = click.option("--noop", type=bool, is_flag=True, default=False,
                    help="If given, DO NOT request signature, "
                    "show the JSON that WOULD be sent over the bus")
ca_certs = click.option("--ca-certs", type=click.Path(exists=True),
                        default=DEFAULT_CA_CHAIN,
                        help="Manually specify the path to the RHIT CA Trust Chain. "
                        "Default: {}".format(DEFAULT_CA_CHAIN))
digest = click.option("--digest", metavar="DIGEST", help="Pass the digest that should be signed")

# ---------------------------------------------------------------------


@click.group(context_settings=context_settings)
def cli(**kwargs):
    """Helper utility for internal Red Hat use ONLY. Use in a build job to
request signatures for various artifacts produced as part of an
Openshift 4.x release. Signatures are requested by sending a JSON blob
over the Universal Message Bus to the 'robosignatory' (RADAS).

You may override the default path to look for the Red Hat IT
Certificate Authority trust chain by using the --ca-certs option in
the global context (before the sub-command).
    """
    pass


######################################################################
# Helpers
def get_digest_base64(location):
    """Download the sha256sum.txt message digest file at the given
`location`.

    :return: A `string` of the base64-encoded message digest
"""
    res = requests.get(location,
                       verify=ssl.get_default_verify_paths().openssl_cafile)
    if res.status_code == 200:
        # b64encode needs a bytes type input, use the dedicated
        # 'encode' method to turn str=>bytes. The result of
        # `b64encode` is a bytes type. Later when we go to serialize
        # this with json it needs to be a str type so we will decode
        # the bytes=>str now.
        return base64.b64encode(res.text.encode()).decode()
    else:
        raise(Exception(res.reason))


def presend_validation(message):
    """Verify the message we want to send over the bus has all the
required fields
    """
    for field in SIGN_REQUEST_MESSAGE_FIELDS:
        if field not in message:
            return field
    return True


def oc_image_info(pullspec):
    """Get metadata for an image at the given `pullspec`

    :return: a dict with the serialzed JSON from the 'oc image info'
call
    """
    image_info_raw = subprocess.check_output(
        ['oc', 'image', 'info', '-o', 'json', pullspec])
    return json.loads(image_info_raw)


def get_bus_producer(env, certificate, private_key, trusted_certificates):
    """This is just a wrapper around creating a producer. We're going to
need this in multiple places so we want to ensure we do it the
same way each time.
    """
    return AMQProducer(urls=URLS[env or 'stage'],
                       certificate=certificate,
                       private_key=private_key,
                       trusted_certificates=trusted_certificates,
                       topic=TOPIC)


def producer_thread(producer, args):
    print(args)
    producer.send_msg(*args)


def producer_send_msg(producer, *args):
    t = threading.Thread(target=producer_thread, args=(producer, args))
    t.start()
    t.join()


def get_bus_consumer(env, certificate, private_key, trusted_certificates):
    """This is just a wrapper around creating a consumer. We're going to
do need this in multiple places though, so we want to ensure we do it
the same way each time.
    """
    return AMQConsumer(urls=URLS[env or 'stage'], certificate=certificate,
                       private_key=private_key, trusted_certificates=trusted_certificates)


def art_consumer_callback(msg, notsure):
    """`msg` is a `Message` object which has various attributes. Such as `body`.

    `notsure` I am not sure what that is. I only got as far as knowing
    this callback requires two parameters.
    """
    print(msg)
    body = json.loads(msg.body)
    print(json.dumps(body, indent=4))
    if body['msg']['signing_status'] != 'success':
        print("ERROR: robosignatory failed to sign artifact")
        exit(1)
    else:
        # example: https://datagrepper.stage.engineering.redhat.com/id?id=2019-0304004b-d1e6-4e03-b28d-cfa1e5f59948&is_raw=true&size=extra-large
        result = body['msg']['signed_artifact']
        out_file = body['msg']['artifact_meta']['name']
        with open(out_file, 'w') as fp:
            fp.write(base64.decodestring(result))
            fp.flush()
        print("Wrote {} to disk".format(body['msg']['artifact_meta']['name']))
        return True


def consumer_thread(consumer):
    consumer.consume(ART_CONSUMER.format(env=env), art_consumer_callback)


def consumer_start(consumer):
    t = threading.Thread(target=consumer_thread, args=(consumer,))
    t.start()
    return t


def get_producer_consumer(env, certificate, private_key, trusted_certificates):
    producer = get_bus_producer(env, certificate, private_key, trusted_certificates)
    consumer = get_bus_consumer(env, certificate, private_key, trusted_certificates)
    return (producer, consumer)


######################################################################
@cli.command("message-digest", short_help="Sign a sha256sum.txt file")
@requestor
@product
@request_id
@sig_keyname
@release_name_opt
@client_cert
@client_key
@client_type
@env
@noop
@ca_certs
@arch_opt
@click.pass_context
def message_digest(ctx, requestor, product, request_id, sig_keyname,
                   release_name, client_cert, client_key, client_type, env, noop,
                   ca_certs, arch):
    """Sign a 'message digest'. These are sha256sum.txt files produced by
the 'sha256sum` command (hence the strange command name). In the ART
world, this is for signing message digests from extracting OpenShift
tools, as well as RHCOS bare-betal message digests.
"""
    if product == 'openshift':
        artifact_url = MESSAGE_DIGESTS[product].format(
            arch=arch,
            release_name=release_name,
            release_stage=client_type)
    elif product == 'rhcos':
        release_parts = release_name.split('.')
        artifact_url = MESSAGE_DIGESTS[product].format(
            arch=arch,
            release_name_xy='.'.join(release_parts[:2]),
            release_name=release_name)

    artifact = get_digest_base64(artifact_url)

    message = {
        "artifact": artifact,
        "artifact_meta": {
            "product": product,
            "release_name": release_name,
            "name": "sha256sum.txt.gpg",
            "type": "message-digest",
        },
        "request_id": request_id,
        "requestor": requestor,
        "sig_keyname": sig_keyname,
    }

    validated = presend_validation(message)
    if validated is True:
        print("Message contains all required fields")
        to_send = json.dumps(message)
    else:
        print("Message missing required field: {}".format(validated))
        exit(1)

    if noop:
        print("Message we would have sent over the bus:")
        print(to_send)
    else:
        producer, consumer = get_producer_consumer(env, client_cert, client_key, ca_certs)
        consumer_thread = consumer_start(consumer)
        producer_send_msg(producer, {}, to_send)
        print("Message we sent over the bus:")
        print(to_send)
        print("Submitted request for signing. The mirror-artifacts job should be triggered when a response is sent back")
        print("Waiting for consumer to receive data back from request")
        consumer_thread.join()


######################################################################
@cli.command("json-digest", short_help="Sign a JSON digest claim")
@requestor
@product
@request_id
@sig_keyname
@release_name_opt
@client_cert
@client_key
@client_type
@env
@noop
@ca_certs
@digest
@arch_opt
@click.pass_context
def json_digest(ctx, requestor, product, request_id, sig_keyname,
                release_name, client_cert, client_key, client_type, env, noop,
                ca_certs, digest, arch):
    """Sign a 'json digest'. These are JSON blobs that associate a
pullspec with a sha256 digest. In the ART world, this is for "signing
payload images". After the json digest is signed we publish the
signature in a location which follows a specific directory pattern,
thus allowing the signature to be looked up programmatically.
    """
    json_claim = {
        "critical": {
            "image": {
                "docker-manifest-digest": None
            },
            "type": "atomic container signature",
            "identity": {
                "docker-reference": None,
            }
        },
        "optional": {
            "creator": "Red Hat OpenShift Signing Authority 0.0.1",
        },
    }

    release_stage = "ocp-release-nightly" if client_type == 'ocp-dev-preview' else "ocp-release"
    release_tag = get_release_tag(release_name, arch)
    pullspec = "quay.io/openshift-release-dev/{}:{}".format(release_stage, release_tag)
    json_claim['critical']['identity']['docker-reference'] = pullspec

    if not digest:
        digest = oc_image_info(pullspec)['digest']

    json_claim['critical']['image']['docker-manifest-digest'] = digest

    print("ARTIFACT to send for signing (WILL BE base64 encoded first):")
    print(json.dumps(json_claim, indent=4))

    message = {
        "artifact": base64.b64encode(json.dumps(json_claim).encode()).decode(),
        "artifact_meta": {
            "product": product,
            "release_name": release_name,
            "name": json_claim['critical']['image']['docker-manifest-digest'].replace(':', '='),
            "type": "json-digest",
        },
        "request_id": request_id,
        "requestor": requestor,
        "sig_keyname": sig_keyname,
    }

    validated = presend_validation(message)
    if validated is True:
        print("Message contains all required fields")
        to_send = json.dumps(message)
    else:
        print("Message missing required field: {}".format(validated))
        exit(1)

    if noop:
        print("Message we would have sent over the bus:")
        print(to_send)
    else:
        producer, consumer = get_producer_consumer(env, client_cert, client_key, ca_certs)
        consumer_thread = consumer_start(consumer)
        producer_send_msg(producer, {}, to_send)
        print("Message we sent over the bus:")
        print(to_send)
        print("Submitted request for signing. The mirror-artifacts job should be triggered when a response is sent back")
        print("Waiting for consumer to receive data back from request")
        consumer_thread.join()

######################################################################


if __name__ == '__main__':
    cli()
