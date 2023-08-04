import asyncio
import logging
import threading
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse
import warnings
import weakref

import stomp
import stomp.utils

_LOGGER = logging.getLogger(__name__)
STOMP_DEFAULT_PORT = 61613


def parse_stomp_uri(uri: str):
    """ Parses a stomp URI.
    Examples:
      stomp://umb.stage.api.redhat.com:61612
      stomp+tcp://umb.stage.api.redhat.com:61612
      stomp+ssl://umb.stage.api.redhat.com:61612
    :param uri: the URI to parse
    :return: (scheme, hostname, port)
    """
    parsed = urlparse(uri)
    if parsed.scheme not in {"stomp", "stomp+tcp", "stomp+ssl"}:
        raise ValueError(f"Unsupported scheme {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("Hostname is required")
    return parsed.scheme, parsed.hostname, parsed.port or STOMP_DEFAULT_PORT


def parse_broker_uri(uri: str):
    """ Parses a broker URI or a failover URI.
    Examples:
      stomp+ssl://umb.stage.api.redhat.com:61612
      failover:(stomp+ssl://umb-broker03.api.redhat.com:61612,stomp+ssl://umb-broker04.api.redhat.com:61612)
    :param uri: the URI to parse
    :return: a list of tuples in format of (scheme, hostname, port)
    """
    parsed = urlparse(uri)
    if parsed.scheme == "failover":
        # URI uses Failover transport https://activemq.apache.org/failover-transport-reference.html
        if not parsed.path:
            raise ValueError(f"Incomplete URI: {uri}")
        if parsed.path[0] == "(" and parsed.path[-1] == ")":  # URI looks like "failover:(<uri1>,<uri2>,...)"
            uris = parsed.path[1:-1].split(",")
        else:  # URI looks like "failover:<uri1>,<uri2>,..."
            uris = parsed.path.split(",")
        return [parse_stomp_uri(uri) for uri in uris]
    return [parse_stomp_uri(uri)]


class AsyncUMBReceiver:
    """ Provides an interface to iterate received messages from the subscription.

    Example:
    ```
    receiver = await umb_client.subscribe(consumer_queue, subscription_name)
    async for message in receiver.iter_messages():
        print(message.headers["message-id"])
    ```
    """

    def __init__(self, id: str) -> None:
        self.id = id
        self._queue: asyncio.Queue[Optional[stomp.utils.Frame]] = asyncio.Queue()
        self._loop = asyncio.get_event_loop()
        self.closed = False

    async def iter_messages(self):
        while True:
            r = await self._queue.get()
            if r is None:  # None represents "EOF"
                return
            yield r

    def put_frame(self, frame: stomp.utils.Frame):
        if self.closed:
            raise ValueError("AsyncUMBReceiver is closed")
        self._queue.put_nowait(frame)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._queue.put_nowait(None)  # None represents "EOF"

    def close_threadsafe(self):
        """ close() is not thread-safe.
        This method can be called from another thread
        to schedule the event loop in the main thread to close it soon.
        """
        self._loop.call_soon_threadsafe(self.close)


class UMBClientConnectionListener(stomp.ConnectionListener):
    """ This class is used internally by AsyncUMBClient to handle stomp.py events.

    stomp.py calls "on_*" methods from a separate thread when an event occurs.
    Be careful to avoid race condition!

    """

    def __init__(self, client: "AsyncUMBClient", print_to_log=True):
        self._client = client
        self._futures: Dict[str, asyncio.Future] = {}
        self._receivers: Dict[str, AsyncUMBReceiver] = {}
        self.print_to_log = print_to_log

    def add_future(self, id: str, fut: asyncio.Future):
        if id in self._futures:
            raise KeyError(f"Future ID {id} already exists")
        self._futures[id] = fut

    def remove_future(self, id: str):
        old = self._futures.pop(id, None)
        if old and not old.done():
            old.cancel()

    def add_receiver(self, id: str, receiver: AsyncUMBReceiver):
        if id in self._receivers:
            raise KeyError(f"Receiver ID {id} already exists")
        self._receivers[id] = receiver

    def remove_receiver(self, id: str, close=True):
        old = self._receivers.pop(id, None)
        if old and close:
            old.close()

    def __print(self, msg, *args):
        if self.print_to_log:
            logging.debug(msg, *args)
        else:
            print(msg % args)

    def on_connecting(self, host_and_port):
        """
        :param (str,int) host_and_port:
        """
        self.__print("on_connecting %s %s", *host_and_port)

    def on_connected(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_connected %s %s", frame.headers, frame.body)
        self._complete_future("on_connected", None)

    def _complete_future(self, id: str, result: Any):
        fut = self._futures.get(id)
        if not fut:
            return
        fut.get_loop().call_soon_threadsafe(fut.set_result, result)

    def _err_future(self, id: str, err: Exception):
        fut = self._futures.get(id)
        if not fut:
            return
        fut.get_loop().call_soon_threadsafe(fut.set_exception, err)

    def on_disconnected(self):
        self.__print("on_disconnected")
        # close all receivers
        for _, r in self._receivers.items():
            r.close_threadsafe()
        # notify UMB client
        self._client.on_disconnected()
        # notify all pending futures of the disconnection
        for future_id in self._futures.keys():
            if future_id == "on_disconnected":
                self._complete_future("on_disconnected", None)
            else:
                self._err_future(future_id, IOError("Connection lost"))

    def on_heartbeat_timeout(self):
        self.__print("on_heartbeat_timeout")

    def on_before_message(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_before_message %s %s", frame.headers, frame.body)

    def on_message(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_message %s %s", frame.headers, frame.body)
        subscription = frame.headers.get("subscription")
        if subscription:
            receiver = self._receivers.get(subscription)
            if receiver:
                receiver._loop.call_soon_threadsafe(receiver.put_frame, frame)

    def on_receipt(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_receipt %s %s", frame.headers, frame.body)
        receipt = frame.headers.get("receipt-id")
        if receipt:
            self._complete_future(receipt, frame)

    def on_error(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_error %s %s", frame.headers, frame.body)

    def on_send(self, frame):
        """
        :param Frame frame: the stomp frame
        """
        self.__print("on_send %s %s %s", frame.cmd, frame.headers, frame.body)

    def on_heartbeat(self):
        self.__print("on_heartbeat")


class AsyncUMBClient:
    """
    AsyncUMBClient provides a simpler interface to send and receive messages
    through UMB (Universal Message Bus).
    For more information about UMB, see https://source.redhat.com/groups/public/enterprise-services-platform/it_platform_wiki/umb_appendix#queues-topics-and-virtualtopics.

    Example:
    ```
    uri = "stomp+ssl://umb.stage.api.redhat.com:61612"
    cert_file = "ssl/nonprod-openshift-art-bot.crt"
    key_file = "ssl/nonprod-openshift-art-bot.key"
    umb_client = AsyncUMBClient(uri, cert_file, key_file)
    await umb_client.connect()
    # send a message
    await umb_client.send(topic, request_body)
    # receive messages
    receiver = await umb_client.subscribe(consumer_queue, subscription_name)
    async for message in receiver.iter_messages():
        print(message.headers["message-id"])
    # disconnect
    await umb_client.disconnect()

    # or use context manager
    async with AsyncUMBClient(uri, cert_file, key_file) as umb_client:
        await umb_client.send(topic, request_body)
        receiver = await umb_client.subscribe(consumer_queue, subscription_name)
        async for message in receiver.iter_messages():
            print(message.headers["message-id"])
    ```
    """

    def __init__(
        self,
        uri: str,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None
    ):
        conn = self._create_connection(uri, cert_file, key_file)
        self._listener = UMBClientConnectionListener(self)
        conn.set_listener("", self._listener)
        self._conn = conn
        self._main_loop = asyncio.get_event_loop()
        self._sender_loop = None
        self._sender_thread = None

    async def close(self):
        await self.disconnect()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __del__(self):
        if self.connected:
            warnings.warn(
                f"Unclosed UMB connection {self!r}", ResourceWarning)

    @property
    def connected(self):
        """ Returns True if already connected
        """
        return self._conn.is_connected()

    def on_disconnected(self):
        """ Handles disconnection.
        This method is called by the listener from another thread.
        """
        def _handle_disconnected():
            if self._sender_loop:
                sender_loop = self._sender_loop
                sender_loop.call_soon_threadsafe(sender_loop.stop)  # This will cause the sender thread to exit
                self._sender_loop = None
                self._sender_thread = None
        self._main_loop.call_soon_threadsafe(_handle_disconnected)

    @staticmethod
    def _sender_thread_func(loop: asyncio.AbstractEventLoop):
        """ Thread function of the sender thread
        :param loop: a loop to be associated with the thread
        """
        # Start an event loop and run until loop.stop() is called
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @staticmethod
    def _create_connection(
        uri: str,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None
    ):
        """ Creates and configures a stomp connection
        """
        parsed_uris = parse_broker_uri(uri)
        host_and_ports = [(hostname, port) for _, hostname, port in parsed_uris]
        conn = stomp.StompConnection11(host_and_ports=host_and_ports)  # UMB supports Stomp v1.1 protocol
        ssl_host_and_ports = [(hostname, port) for scheme, hostname, port in parsed_uris if scheme == "stomp+ssl"]
        if ssl_host_and_ports:
            conn.set_ssl(for_hosts=ssl_host_and_ports, cert_file=cert_file, key_file=key_file)
        return conn

    async def _call_in_sender_thread(self, func: Callable):
        """ Calls a function in the sender thread (thread-safe)
        :param func: the function to call
        :return: return value of the function call
        """
        if not self._sender_loop:
            raise IOError("Not connected")
        fut = self._main_loop.create_future()

        def callback():
            try:
                result = func()
                fut.get_loop().call_soon_threadsafe(fut.set_result, result)
            except Exception as ex:
                fut.get_loop().call_soon_threadsafe(fut.set_exception, ex)
        self._sender_loop.call_soon_threadsafe(callback)
        return await fut

    async def connect(self):
        if self.connected:
            raise IOError("Already connected")
        _LOGGER.info("Connecting to message bus...")
        if not self._sender_loop:
            self._sender_loop = asyncio.new_event_loop()
            self._sender_thread = threading.Thread(target=self._sender_thread_func, args=(self._sender_loop, ), daemon=True)
            self._sender_thread.start()
        receipt = str(uuid.uuid4())
        fut = self._main_loop.create_future()
        self._listener.add_future("on_connected", fut)
        try:
            await self._call_in_sender_thread(lambda: self._conn.connect(wait=False, headers={"receipt": receipt}))
            await fut
        finally:
            self._listener.remove_future("on_connected")
        _LOGGER.info("Connected")

    async def disconnect(self):
        """ Disconnect from the message broker and wait for the receipt
        """
        if not self.connected:
            return
        _LOGGER.info("Disconnecting from message bus...")
        receipt = str(uuid.uuid4())
        fut = self._main_loop.create_future()
        self._listener.add_future("on_disconnected", fut)
        try:
            await self._call_in_sender_thread(lambda: self._conn.disconnect(receipt=receipt))
            await fut
        finally:
            self._listener.remove_future("on_disconnected")
        _LOGGER.info("Disconnected")

    async def subscribe(self, destination: str, id: str):
        """ Subscribe to a destination
        :param destination: a queue or topic
        :param id: subscription ID
        :return: an instance of AsyncUMBReceiver for receiving messages for the subscription
        """
        subscription_id = id or str(uuid.uuid4())
        receiver = AsyncUMBReceiver(id=subscription_id)
        self._listener.add_receiver(subscription_id, receiver)
        await self._call_in_sender_thread(lambda: self._conn.subscribe(destination=destination, id=subscription_id, ack="client-individual"))
        return receiver

    async def unsubscribe(self, id: str):
        """ Unsubscribes from the queue or topic
        :param id: subscription ID
        """
        receiver = self._listener._receivers.get(id)
        if not receiver:
            raise ValueError(f"Subscription '{id}' doesn't exist")
        await self._call_in_sender_thread(lambda: self._conn.unsubscribe(id=id))
        self._listener.remove_receiver(id, close=True)

    async def send(self, destination: str, body: str):
        """ Sends a message to the broker and wait for the receipt
        """
        receipt = str(uuid.uuid4())
        _LOGGER.debug("Sending message %s to %s...", body, destination)
        fut = self._main_loop.create_future()
        self._listener.add_future(receipt, fut)
        try:
            await self._call_in_sender_thread(lambda: self._conn.send(
                body=body,
                destination=destination,
                headers={"receipt": receipt},
            ))
            await fut
        finally:
            self._listener.remove_future(receipt)

    async def ack(self, message_id: str, subscription: str):
        """ Acknowledges 'consumption' of a message by id.
        """
        receipt = str(uuid.uuid4())
        fut = self._main_loop.create_future()
        self._listener.add_future(receipt, fut)
        try:
            await self._call_in_sender_thread(lambda: self._conn.ack(message_id, subscription, receipt=receipt))
            await fut
        finally:
            self._listener.remove_future(receipt)

    async def nack(self, message_id: str, subscription: str):
        """ Notifies the message broker that a message was not consumed.
        """
        receipt = str(uuid.uuid4())
        fut = self._main_loop.create_future()
        self._listener.add_future(receipt, fut)
        try:
            await self._call_in_sender_thread(lambda: self._conn.nack(message_id, subscription, receipt=receipt))
            await fut
        finally:
            self._listener.remove_future(receipt)
