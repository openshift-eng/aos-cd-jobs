import asyncio
import base64
from datetime import datetime, timezone
from io import BytesIO
import json
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from pyartcd.signatory import AsyncSignatory


class TestAsyncSignatory(IsolatedAsyncioTestCase):
    @patch("aiofiles.open", autospec=True)
    async def test_get_certificate_common_name(self, open: AsyncMock):
        # Well, this is the content of "Red Hat IT Root CA"
        open.return_value.__aenter__.return_value.read.return_value = b"""
-----BEGIN CERTIFICATE-----
MIIENDCCAxygAwIBAgIJANunI0D662cnMA0GCSqGSIb3DQEBCwUAMIGlMQswCQYD
VQQGEwJVUzEXMBUGA1UECAwOTm9ydGggQ2Fyb2xpbmExEDAOBgNVBAcMB1JhbGVp
Z2gxFjAUBgNVBAoMDVJlZCBIYXQsIEluYy4xEzARBgNVBAsMClJlZCBIYXQgSVQx
GzAZBgNVBAMMElJlZCBIYXQgSVQgUm9vdCBDQTEhMB8GCSqGSIb3DQEJARYSaW5m
b3NlY0ByZWRoYXQuY29tMCAXDTE1MDcwNjE3MzgxMVoYDzIwNTUwNjI2MTczODEx
WjCBpTELMAkGA1UEBhMCVVMxFzAVBgNVBAgMDk5vcnRoIENhcm9saW5hMRAwDgYD
VQQHDAdSYWxlaWdoMRYwFAYDVQQKDA1SZWQgSGF0LCBJbmMuMRMwEQYDVQQLDApS
ZWQgSGF0IElUMRswGQYDVQQDDBJSZWQgSGF0IElUIFJvb3QgQ0ExITAfBgkqhkiG
9w0BCQEWEmluZm9zZWNAcmVkaGF0LmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBALQt9OJQh6GC5LT1g80qNh0u50BQ4sZ/yZ8aETxt+5lnPVX6MHKz
bfwI6nO1aMG6j9bSw+6UUyPBHP796+FT/pTS+K0wsDV7c9XvHoxJBJJU38cdLkI2
c/i7lDqTfTcfLL2nyUBd2fQDk1B0fxrskhGIIZ3ifP1Ps4ltTkv8hRSob3VtNqSo
GxkKfvD2PKjTPxDPWYyruy9irLZioMffi3i/gCut0ZWtAyO3MVH5qWF/enKwgPES
X9po+TdCvRB/RUObBaM761EcrLSM1GqHNueSfqnho3AjLQ6dBnPWlo638Zm1VebK
BELyhkLWMSFkKwDmne0jQ02Y4g075vCKvCsCAwEAAaNjMGEwHQYDVR0OBBYEFH7R
4yC+UehIIPeuL8Zqw3PzbgcZMB8GA1UdIwQYMBaAFH7R4yC+UehIIPeuL8Zqw3Pz
bgcZMA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgGGMA0GCSqGSIb3DQEB
CwUAA4IBAQBDNvD2Vm9sA5A9AlOJR8+en5Xz9hXcxJB5phxcZQ8jFoG04Vshvd0e
LEnUrMcfFgIZ4njMKTQCM4ZFUPAieyLx4f52HuDopp3e5JyIMfW+KFcNIpKwCsak
oSoKtIUOsUJK7qBVZxcrIyeQV2qcYOeZhtS5wBqIwOAhFwlCET7Ze58QHmS48slj
S9K0JAcps2xdnGu0fkzhSQxY8GPQNFTlr6rYld5+ID/hHeS76gq0YG3q6RLWRkHf
4eTkRjivAlExrFzKcljC4axKQlnOvVAzz+Gm32U0xPBF4ByePVxCJUHw1TsyTmel
RxNEp7yHoXcwn+fXna+t5JWh1gxUZty3
-----END CERTIFICATE-----
"""
        actual = await AsyncSignatory._get_certificate_common_name("/path/to/client.crt")
        self.assertEqual(actual, "Red Hat IT Root CA")

    @patch("pyartcd.signatory.AsyncSignatory._get_certificate_common_name", autospec=True)
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_start(self, AsyncUMBClient: AsyncMock, _get_certificate_common_name: AsyncMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        _get_certificate_common_name.return_value = "fake-service-account"
        umb = AsyncUMBClient.return_value
        receiver = umb.subscribe.return_value

        async def iter_messages():
            for item in range(3):
                yield f"message-{item}"
            return
        receiver.iter_messages.side_effect = iter_messages
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        await signatory.start()
        umb.subscribe.assert_awaited_once_with("/queue/Consumer.fake-service-account.fake-subscription.VirtualTopic.eng.robosignatory.art.sign", "fake-subscription")

    @patch("pyartcd.signatory.datetime", wraps=datetime)
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_handle_messages_with_stale_message(self, AsyncUMBClient: AsyncMock, datetime: MagicMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        receiver = signatory._receiver = MagicMock(id="fake-subscription")
        datetime.utcnow.return_value = datetime(2023, 1, 2, 0, 0, 0)

        async def iter_messages():
            messages = [
                MagicMock(
                    headers={"message-id": "fake-message-id", "timestamp": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000},
                    body="")
            ]
            for item in messages:
                yield item
        receiver.iter_messages.side_effect = iter_messages
        umb = AsyncUMBClient.return_value

        await signatory._handle_messages()

        umb.ack.assert_awaited_once_with("fake-message-id", "fake-subscription")

    @patch("pyartcd.signatory.datetime", wraps=datetime)
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_handle_messages_with_invalid_message(self, AsyncUMBClient: AsyncMock, datetime: MagicMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        receiver = signatory._receiver = MagicMock(id="fake-subscription")
        datetime.utcnow.return_value = datetime(2023, 1, 1, 0, 1, 0)

        async def iter_messages():
            messages = [
                MagicMock(
                    headers={"message-id": "fake-message-id", "timestamp": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000},
                    body="")
            ]
            for item in messages:
                yield item
        receiver.iter_messages.side_effect = iter_messages
        umb = AsyncUMBClient.return_value

        await signatory._handle_messages()

        umb.ack.assert_not_called()

    @patch("pyartcd.signatory.datetime", wraps=datetime)
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_handle_messages_with_valid_message(self, AsyncUMBClient: AsyncMock, datetime: MagicMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        receiver = signatory._receiver = MagicMock(id="fake-subscription")
        datetime.utcnow.return_value = datetime(2023, 1, 1, 0, 1, 0)
        signatory._requests["fake-request-id"] = asyncio.get_event_loop().create_future()

        async def iter_messages():
            messages = [
                MagicMock(
                    headers={"message-id": "fake-message-id", "timestamp": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000},
                    body=json.dumps({"msg": {"request_id": "fake-request-id"}}))
            ]
            for item in messages:
                yield item
        receiver.iter_messages.side_effect = iter_messages
        umb = AsyncUMBClient.return_value

        await signatory._handle_messages()

        umb.ack.assert_awaited_once_with("fake-message-id", "fake-subscription")
        message_headers, message_body = await signatory._requests["fake-request-id"]
        self.assertEqual(message_headers["message-id"], "fake-message-id")
        self.assertEqual(message_body["msg"]["request_id"], "fake-request-id")

    @patch("pyartcd.signatory.datetime", wraps=datetime)
    @patch("uuid.uuid4", autospec=True)
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_sign_artifact(self, AsyncUMBClient: AsyncMock, uuid4: MagicMock, datetime: MagicMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        artifact = BytesIO(b"fake_artifact")
        sig_file = BytesIO()
        uuid4.return_value = "fake-uuid"
        datetime.utcnow.return_value = datetime(2023, 1, 2, 12, 30, 40)
        umb = AsyncUMBClient.return_value
        response_headers = {}
        response_body = {
            "msg": {
                "artifact_meta": {
                    "name": "sha256sum.txt.gpg",
                    "product": "openshift",
                    "release_name": "4.0.1",
                    "type": "message-digest"
                },
                "signing_status": "success",
                "errors": [],
                "signed_artifact": base64.b64encode(b'fake-signature').decode()}
        }
        expected_requested_id = 'openshift-message-digest-20230102123040-fake-uuid'
        asyncio.get_event_loop().call_soon(lambda: signatory._requests[expected_requested_id].set_result((response_headers, response_body)))

        await signatory._sign_artifact("message-digest", "openshift", "4.0.1", "sha256sum.txt.gpg", artifact, sig_file)
        umb.send.assert_awaited_once_with(signatory.SEND_DESTINATION, ANY)
        self.assertEqual(sig_file.getvalue(), b'fake-signature')

    @patch("pyartcd.signatory.AsyncSignatory._sign_artifact")
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_sign_message_digest(self, AsyncUMBClient: AsyncMock, _sign_artifact: AsyncMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        artifact = BytesIO(b"fake_artifact")
        sig_file = BytesIO()
        _sign_artifact.side_effect = lambda *args, **kwargs: sig_file.write(b"fake-signature")

        await signatory.sign_message_digest("openshift", "4.0.1", artifact, sig_file)
        _sign_artifact.assert_awaited_once_with(typ='message-digest', product='openshift', release_name='4.0.1', name='sha256sum.txt.gpg', artifact=artifact, sig_file=sig_file)
        self.assertEqual(sig_file.getvalue(), b'fake-signature')

    @patch("pyartcd.signatory.AsyncSignatory._sign_artifact")
    @patch("pyartcd.signatory.AsyncUMBClient", autospec=True)
    async def test_sign_json_digest(self, AsyncUMBClient: AsyncMock, _sign_artifact: AsyncMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        signatory = AsyncSignatory(uri, cert_file, key_file, sig_keyname="test", requestor="fake-requestor", subscription_name="fake-subscription")
        sig_file = BytesIO()
        _sign_artifact.side_effect = lambda *args, **kwargs: sig_file.write(b"fake-signature")
        pullspec = "example.com/fake/repo@sha256:dead-beef"

        await signatory.sign_json_digest("openshift", "4.0.1", pullspec, "sha256:dead-beef", sig_file)
        _sign_artifact.assert_awaited_once_with(typ='json-digest', product='openshift', release_name='4.0.1', name='sha256=dead-beef', artifact=ANY, sig_file=sig_file)
        self.assertEqual(sig_file.getvalue(), b'fake-signature')
