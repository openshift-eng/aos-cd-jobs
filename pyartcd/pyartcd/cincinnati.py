from typing import Optional

from aiohttp import ClientSession
from aiohttp_retry import ExponentialRetry, RetryClient

CINCINNATI_DEFAULT_URL = "https://api.openshift.com"


class CincinnatiAPI:
    def __init__(self, server: Optional[str] = CINCINNATI_DEFAULT_URL, session: Optional[ClientSession] = None) -> None:
        self._server = server
        self._client = RetryClient(client_session=session, retry_options=ExponentialRetry(attempts=10))

    async def get_graph(self, channel: str, arch: Optional[str] = None):
        url = f"{self._server}/api/upgrades_info/v1/graph"
        params = dict(channel=channel)
        if arch:
            params["arch"] = arch
        async with self._client.get(url, headers={'Accept': 'application/json'}, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            return data
