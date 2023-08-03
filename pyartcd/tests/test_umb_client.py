import asyncio
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import ANY, MagicMock, patch

from pyartcd.umb_client import AsyncUMBClient, parse_stomp_uri, parse_broker_uri


class TestModuleFunctions(TestCase):
    def test_parse_stomp_uri_with_default_port(self):
        uri = "stomp://broker.example.com"
        expected = ("stomp", "broker.example.com", 61613)
        actual = parse_stomp_uri(uri)
        self.assertEqual(actual, expected)

    def test_parse_stomp_uri_with_port(self):
        uri = "stomp+ssl://broker.example.com:12345"
        expected = ("stomp+ssl", "broker.example.com", 12345)
        actual = parse_stomp_uri(uri)
        self.assertEqual(actual, expected)

    def test_parse_stomp_uri_with_invalid_scheme(self):
        uri = "unsupported://broker.example.com:12345"
        with self.assertRaises(ValueError):
            parse_stomp_uri(uri)

    def test_parse_broker_uri_with_stomp_scheme(self):
        uri = "stomp+ssl://broker.example.com:12345"
        expected = [("stomp+ssl", "broker.example.com", 12345)]
        actual = parse_broker_uri(uri)
        self.assertEqual(actual, expected)

    def test_parse_broker_uri_with_failover_scheme(self):
        uri = "failover:stomp+ssl://broker1.example.com:12345,stomp+ssl://broker2.example.com:12345"
        expected = [("stomp+ssl", "broker1.example.com", 12345), ("stomp+ssl", "broker2.example.com", 12345)]
        actual = parse_broker_uri(uri)
        self.assertEqual(actual, expected)


class TestAsyncUMBClient(IsolatedAsyncioTestCase):

    @patch("stomp.StompConnection11", autospec=True)
    def test_create_connection(self, StompConnection11: MagicMock):
        uri = "failover:(stomp+ssl://stomp1.example.com:12345,stomp://stomp2.example.com:23456)"
        cert_file = "/path/to/client.crt"
        key_file = "/path/to/client.key"
        actual = AsyncUMBClient._create_connection(uri, cert_file, key_file)
        conn = StompConnection11.return_value
        self.assertEqual(actual, conn)
        StompConnection11.assert_called_once_with(host_and_ports=[("stomp1.example.com", 12345), ("stomp2.example.com", 23456)])
        conn.set_ssl.assert_called_once_with(for_hosts=[("stomp1.example.com", 12345)], cert_file=cert_file, key_file=key_file)

    async def test_call_in_sender_thread(self):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        client._sender_loop = asyncio.get_event_loop()
        actual = await client._call_in_sender_thread(lambda: "foo")
        self.assertEqual(actual, "foo")

    async def test_call_in_sender_thread_with_exception(self):
        def func():
            raise ValueError("Test error")
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        client._sender_loop = asyncio.get_event_loop()
        with self.assertRaises(ValueError):
            await client._call_in_sender_thread(func)

    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_connect(self, _create_connection: MagicMock):
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = False
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        loop = asyncio.get_event_loop()
        loop.call_soon(lambda: client._listener._complete_future("on_connected", None))
        await client.connect()
        conn = _create_connection.return_value
        conn.connect.assert_called_once_with(wait=False, headers={"receipt": ANY})

    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_disconnect(self, _create_connection: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        loop = asyncio.get_event_loop()
        loop.call_soon(lambda: client._listener._complete_future("on_disconnected", None))
        await client.disconnect()
        conn = _create_connection.return_value
        conn.disconnect.assert_called_once_with(receipt=ANY)

    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_subscribe(self, _create_connection: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        receiver = await client.subscribe(destination="/topic/foo.bar", id="fake-subscription")
        conn = _create_connection.return_value
        conn.subscribe.assert_called_once_with(destination="/topic/foo.bar", id="fake-subscription", ack="client-individual")
        self.assertEqual(receiver.id, "fake-subscription")

    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_unsubscribe(self, _create_connection: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        client._listener._receivers["fake-subscription"] = MagicMock()
        await client.unsubscribe(id="fake-subscription")
        conn = _create_connection.return_value
        conn.unsubscribe.assert_called_once_with(id="fake-subscription")

    @patch("uuid.uuid4", autospec=True)
    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_send(self, _create_connection: MagicMock, uuid4: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        uuid4.return_value = "fake-uuid"
        loop = asyncio.get_event_loop()
        loop.call_soon(lambda: client._listener._complete_future(uuid4.return_value, None))
        await client.send(destination="/topic/foo.bar", body="fake-content")
        conn = _create_connection.return_value
        conn.send.assert_called_once_with(body="fake-content", destination="/topic/foo.bar", headers={"receipt": uuid4.return_value})

    @patch("uuid.uuid4", autospec=True)
    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_ack(self, _create_connection: MagicMock, uuid4: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        uuid4.return_value = "fake-uuid"
        loop = asyncio.get_event_loop()
        loop.call_soon(lambda: client._listener._complete_future(uuid4.return_value, None))
        await client.ack(message_id="fake-message-id", subscription="fake-subscription")
        conn = _create_connection.return_value
        conn.ack.assert_called_once_with("fake-message-id", "fake-subscription", receipt=uuid4.return_value)

    @patch("uuid.uuid4", autospec=True)
    @patch("pyartcd.umb_client.AsyncUMBClient._create_connection", autospec=True)
    async def test_nack(self, _create_connection: MagicMock, uuid4: MagicMock):
        client = AsyncUMBClient("stomp+ssl://stomp1.example.com:12345", cert_file="/path/to/client.crt", key_file="/path/to/client.key")
        stomp_conn = _create_connection.return_value
        stomp_conn.is_connected.return_value = True
        client._sender_loop = asyncio.get_event_loop()
        uuid4.return_value = "fake-uuid"
        loop = asyncio.get_event_loop()
        loop.call_soon(lambda: client._listener._complete_future(uuid4.return_value, None))
        await client.nack(message_id="fake-message-id", subscription="fake-subscription")
        conn = _create_connection.return_value
        conn.nack.assert_called_once_with("fake-message-id", "fake-subscription", receipt=uuid4.return_value)
