#!/usr/bin/env python
import base64
import json
import logging
import ssl
import subprocess
import sys

import click
import requests
from rhmsg.activemq.producer import AMQProducer

# Expose errors during signing for debugging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

######################################################################
URLS = {
    'dev': (
        'amqps://messaging-devops-broker01.dev1.ext.devlab.redhat.com:5671',
        'amqps://messaging-devops-broker02.dev1.ext.devlab.redhat.com:5671',
    ),
    'qa': (
        'amqps://messaging-devops-broker01.web.qa.ext.phx1.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.qa.ext.phx1.redhat.com:5671',
    ),
    'stage': (
        'amqps://messaging-devops-broker01.web.stage.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.stage.ext.phx2.redhat.com:5671',
    ),
    'prod': (
        'amqps://messaging-devops-broker01.web.prod.ext.phx2.redhat.com:5671',
        'amqps://messaging-devops-broker02.web.prod.ext.phx2.redhat.com:5671',
    ),

}

TOPIC = 'VirtualTopic.eng.art.artifact.sign'

# TODO: In the future we need to handle 'rhcos' having '4.1'
# hard-coded into the URL path.
MESSAGE_DIGESTS = {
    'openshift': 'https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{release_name}/sha256sum.txt',
    'rhcos': 'https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/4.1/{release_name}/'
}
DEFAULT_CA_CHAIN = "/etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt"
# HTTP endpoint to get metadata about the latest stable 4.x payload
#
# NOTE: Only accounts for one minor ('Y' in X.Y, eg: '4.1' => '1')
PAYLOAD_META = "https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/4-stable/latest"
# This is the JSON we send OVER the bus when requesting signatures
SIGN_REQUEST_MESSAGE_FIELDS = [
    "artifact",
    # Added by ART
    "artifact_meta",
    "request_id",
    "requestor",
    "sig_keyname",
]


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
release_name = click.option("--release-name", required=True, metavar="SEMVER",
                            help="Numerical name of this release, for example: 4.1.0-rc.10")
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


def get_payload_meta():
    """Get the releasestream metadata for the payload.

    :return: A `dict` of the JSON at the release stream endpoint
"""
    res = requests.get(PAYLOAD_META,
                       verify=ssl.get_default_verify_paths().openssl_cafile)
    if res.status_code == 200:
        return res.json()
    else:
        raise Exception(res.reason)


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


######################################################################
@cli.command("message-digest", short_help="Sign a sha256sum.txt file")
@requestor
@product
@request_id
@sig_keyname
@release_name
@client_cert
@client_key
@env
@noop
@ca_certs
@click.pass_context
def message_digest(ctx, requestor, product, request_id, sig_keyname,
                   release_name, client_cert, client_key, env, noop,
                   ca_certs):
    """Sign a 'message digest'. These are sha256sum.txt files produced by
the 'sha256sum` command (hence the strange command name). In the ART
world, this is for signing message digests from extracting OpenShift
tools, as well as RHCOS bare-betal message digests.
    """
    message = {
        "artifact": get_digest_base64(MESSAGE_DIGESTS[product].format(
            release_name=release_name)),
        "artifact_meta": {
            "product": product,
            "release_name": release_name,
            "name": "sha256sum.txt.sig",
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
        producer = get_bus_producer(env, client_cert, client_key, ca_certs)
        producer.send_msg({}, to_send)
        print("Message we sent over the bus:")
        print(to_send)
        print("Submitted request for signing. The mirror-artifacts job should be triggered when a response is sent back")


######################################################################
@cli.command("json-digest", short_help="Sign a JSON digest claim")
@requestor
@product
@request_id
@sig_keyname
@release_name
@client_cert
@client_key
@env
@noop
@ca_certs
@click.pass_context
def json_digest(ctx, requestor, product, request_id, sig_keyname,
                release_name, client_cert, client_key, env, noop,
                ca_certs):
    """Sign a 'json digest'. These are JSON blobs that associate a
pullspec with a sha256 digest. In the ART world, this is for "signing
payload images". After the json digest is signed we publish the
signature in a location which follows a specific directory pattern,
thus allowing the signature to be looked up programmatically.
    """
    # NOTE: The example claim JSON I've seen includes an 'optional' section
    # like this (same level as 'critical'):
    #
    # "optional": {
    #     "creator": "Red Hat RCM Pub 0.21.0-final "
    # }
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
    }

    payload_meta = get_payload_meta()
    if payload_meta['name'] != release_name:
        print("!!!!! ONLY SIGN THINGS YOU INTEND TO RELEASE !!!!!")
        print("ERROR: Release stream 'name' does not match given release name")
        print("\t{} != {}".format(payload_meta['name'], release_name))
        print("IF YOU INTEND TO RELEASE {} THEN YOU MUST UPDATE THE RELEASE STREAM TAG".format(
            release_name))
        print("Current release stream: {}".format(json.dumps(payload_meta, indent=4)))
        exit(1)
    else:
        print("Given release name matches 4-stable release stream (this is required to continue)")

    image_meta = oc_image_info(payload_meta['pullSpec'])
    json_claim['critical']['image']['docker-manifest-digest'] = image_meta['digest']
    json_claim['critical']['identity']['docker-reference'] = payload_meta['pullSpec']

    print("ARTIFACT to send for signing (WILL BE base64 encoded first):")
    print(json.dumps(json_claim, indent=4))


    message = {
        "artifact": base64.b64encode(json.dumps(json_claim).encode()).decode(),
        "artifact_meta": {
            "product": product,
            "release_name": release_name,
            "name": image_meta['digest'].replace(':', '='),
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
        producer = get_bus_producer(env, client_cert, client_key, ca_certs)
        producer.send_msg({}, to_send)
        print("Message we sent the bus:")
        print(to_send)
        print("Submitted request for signing. The mirror-artifacts job should be triggered when a response is sent back")

######################################################################

if __name__ == '__main__':
    cli()
