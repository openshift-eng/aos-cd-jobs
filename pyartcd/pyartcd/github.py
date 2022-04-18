
import os
from typing import Optional
from urllib.parse import quote

import aiohttp

from pyartcd.exectools import cmd_assert_async


class GitHubAPI:
    def __init__(self, github_token: Optional[str] = None) -> None:
        if not github_token:
            github_token = os.environ.get("GITHUB_TOKEN")
        self._github_token = github_token
        self._headers = {
            "Content-Type": "application/json",
        }
        if self._github_token:
            self._headers["Authorization"] = f"token {self._github_token}"

    async def add_comment(self, message: str, repo_name: str, pr: int):
        url = f"https://api.github.com/repos/{quote(repo_name)}/issues/{pr}/comments"
        data = {"body": message}
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.post(url, json=data) as response:
                content = await response.json()
                response.raise_for_status()
                return content
