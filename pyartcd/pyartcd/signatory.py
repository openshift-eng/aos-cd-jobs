
import asyncio
import base64
import io
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, cast

import aiofiles
from cryptography import x509
from cryptography.x509.oid import NameOID

from pyartcd.exceptions import SignatoryServerError
from pyartcd.umb_client import AsyncUMBClient

_LOGGER = logging.getLogger(__name__)


class AsyncSignatory:
    """
    AsyncSignatory can sign OCP artifacts by sending a signing request to RADAS over UMB.

    Example usage:
    ```
    uri = "stomp+ssl://umb.stage.api.redhat.com:61612"
    cert_file = "ssl/nonprod-openshift-art-bot.crt"
    key_file = "ssl/nonprod-openshift-art-bot.key"
    async with AsyncSignatory(uri, cert_file, key_file, sig_keyname="beta2", requestor="yuxzhu") as signatory:
        pullspec = "quay.io/openshift-release-dev/ocp-release:4.11.31-x86_64"
        digest = "sha256:cc10900ad98b44ba432bc0d99e7d4fffb5498fd6844fc3b6a0a3552ee6d64059"
        # sign a release payload
        with open("signature-1", "wb") as sig_file:
            await signatory.sign_json_digest("openshift", "4.11.31", pullspec, digest, sig_file)
        # sign a message digest
        with open("sha256sum.txt", "rb") as in_file, open("sha256sum.txt.gpg", "wb") as sig_file:
            await signatory.sign_message_digest("openshift", "4.11.31", in_file, sig_file)
    ```
    """

    SEND_DESTINATION = '/topic/VirtualTopic.eng.art.artifact.sign'
    CONSUMER_QUEUE_TEMPLATE = "/queue/Consumer.{service_account}.{subscription}.VirtualTopic.eng.robosignatory.art.sign"

    def __init__(
        self,
        uri: str,
        cert_file: str,
        key_file: str,
        sig_keyname="test",
        requestor="timer",
        subscription_name="artcd",
    ):
        self.cert_file = cert_file
        self.sig_keyname = sig_keyname
        self.requestor = requestor
        self.subscription_name = subscription_name
        self._umb = AsyncUMBClient(uri, cert_file, key_file)
        self._receiver = None
        self._receiver_task = None
        self._requests: Dict[str, asyncio.Future] = {}
        self._loop = asyncio.get_event_loop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @staticmethod
    async def _get_certificate_common_name(cert_file: str):
        """ Get common name for the specified certificate file
        """
        async with aiofiles.open(cert_file, "rb") as f:
            cert = x509.load_pem_x509_certificate(await f.read())
        return cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value

    async def start(self):
        # Get service account name embedded in the client certificate
        service_account = await self._get_certificate_common_name(self.cert_file)
        _LOGGER.info("Using UMB service account: %s", service_account)
        # Connect to UMB
        await self._umb.connect()
        # Subscribe to the consumer queue
        # e.g. /queue/Consumer.openshift-art-bot.artcd.VirtualTopic.eng.robosignatory.art.sign
        consumer_queue = self.CONSUMER_QUEUE_TEMPLATE.format_map({
            "service_account": service_account,
            "subscription": self.subscription_name
        })
        self._receiver = await self._umb.subscribe(consumer_queue, self.subscription_name)
        # Start a task to handle messages received from the consumer queue
        self._receiver_task = asyncio.create_task(self._handle_messages())

    async def close(self):
        """ Closes connection to UMB
        """
        await self._umb.close()
        # self._receiver_task will stop until receives EOF or it was garbage collected
        self._receiver_task = None
        self._receiver = None

    async def _handle_messages(self):
        """ Handles messages received from the consumer queue
        """
        receiver = self._receiver
        assert receiver, "start() was not called"
        async for message in receiver.iter_messages():
            message_id = str(message.headers["message-id"])
            timestamp = int(message.headers["timestamp"]) / 1000
            try:
                age = datetime.utcnow() - datetime.utcfromtimestamp(timestamp)
                if age >= timedelta(hours=1):
                    _LOGGER.warning("Discarding stale message {}".format(message_id))
                    await self._umb.ack(message_id, receiver.id)  # discard the message
                    continue
                body = json.loads(str(message.body))
                request_id = body["msg"]["request_id"]
                fut = self._requests.get(request_id)
                if not fut:
                    _LOGGER.warning("Unknown request_id %s in message %s", request_id, message_id)
                    continue
                fut.set_result((message.headers, body))
                await self._umb.ack(message_id, receiver.id)  # consume the message
            except Exception:
                _LOGGER.exception("Error handling message %s", message_id)
        _LOGGER.info("_handle_message: exited")

    async def _sign_artifact(
        self,
        typ: str,
        product: str,
        release_name: str,
        name: str,
        artifact: BinaryIO,
        sig_file: BinaryIO,
    ):
        """ Signs an artifact
        """
        # Create a signing request
        # Example request: https://datagrepper.stage.engineering.redhat.com/id?id=ID:umb-stage-3.umb-001.preprod.us-east-1.aws.redhat.com-38533-1689629292398-10:23520:-1:1:1&is_raw=true&size=extra-large
        artifact_base64 = io.BytesIO()
        base64.encode(artifact, artifact_base64)
        request_id = (
            f'{product}-{typ}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4()}'
        )
        message = {
            "artifact": artifact_base64.getvalue().decode(),
            "artifact_meta": {
                "product": product,
                "release_name": release_name,
                "name": name,
                "type": typ,
            },
            "request_id": request_id,
            "requestor": self.requestor,
            "sig_keyname": self.sig_keyname,
        }
        request_body = json.dumps(message)

        # Send the signing request via UMB
        fut = self._loop.create_future()
        self._requests[request_id] = fut
        try:
            await self._umb.send(self.SEND_DESTINATION, request_body)
            _, response_body = await fut
        finally:
            del self._requests[request_id]

        # example response: https://datagrepper.stage.engineering.redhat.com/id?id=2019-0304004b-d1e6-4e03-b28d-cfa1e5f59948&is_raw=true&size=extra-large
        if response_body["msg"]["signing_status"] != "success":
            err = ", ".join(response_body["msg"]["errors"])
            raise SignatoryServerError(f"Robo Signatory declined: {err}")
        input = io.BytesIO(response_body["msg"]["signed_artifact"].encode())
        base64.decode(input, sig_file)
        artifact_meta = cast(Dict[str, str], response_body["msg"]["artifact_meta"])
        return artifact_meta

    async def sign_json_digest(
        self, product: str, release_name: str, pullspec: str, digest: str, sig_file: BinaryIO
    ):
        """ Sign a JSON digest claim
        """
        json_claim = {
            "critical": {
                "image": {"docker-manifest-digest": digest},
                "type": "atomic container signature",
                "identity": {
                    "docker-reference": pullspec,
                },
            },
            "optional": {
                "creator": "Red Hat OpenShift Signing Authority 0.0.1",
            },
        }
        artifact = io.BytesIO(json.dumps(json_claim).encode())
        name = digest.replace(":", "=")
        signature_meta = await self._sign_artifact(
            typ="json-digest",
            product=product,
            release_name=release_name,
            name=name,
            artifact=artifact,
            sig_file=sig_file,
        )
        return signature_meta

    async def sign_message_digest(
        self, product: str, release_name: str, artifact: BinaryIO, sig_file: BinaryIO
    ):
        """ Sign a message digest
        """
        name = "sha256sum.txt.gpg"
        signature_meta = await self._sign_artifact(
            typ="message-digest",
            product=product,
            release_name=release_name,
            name=name,
            artifact=artifact,
            sig_file=sig_file,
        )
        return signature_meta
