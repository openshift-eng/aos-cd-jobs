import logging
import re
from typing import Optional

from slack_sdk.web.async_client import AsyncWebClient

_LOGGER = logging.getLogger(__name__)

class SlackClient:
    """ A SlackClient allows pipelines to send Slack messages.
    """
    DEFAULT_CHANNEL = "#art-release"
    def __init__(self, token: str, job_name: Optional[str], job_run_name: Optional[str], job_run_url: Optional[str], dry_run: bool = False) -> None:
        self.token = token
        self.channel = self.DEFAULT_CHANNEL
        self.job_name = job_name
        self.job_run_name = job_run_name
        self.job_run_url = job_run_url
        self.dry_run = dry_run
        self.as_user = "art-release-bot"
        self.icon_emoji = ":robot_face:"
        self._client = AsyncWebClient(token=token)

    def bind_channel(self, channel_or_release: Optional[str]):
        """ Bind this SlackClient to a specified Slack channel. Future messages will be sent to that channel.
        :param channel_or_release: An explicit channel name ('#art-team') or a string that contains a prefix of the
        release the jobs is associated with (e.g. '4.5.2-something' => '4.5'). If a release is specified, the
        slack channel will be #art-release-MAJOR-MINOR. If None or empty string is specified, the slack channel will be the default channel.
        """
        if not channel_or_release:
            self.channel = self.DEFAULT_CHANNEL
            return
        if channel_or_release.startswith("#"):
            self.channel = channel_or_release
            return
        match = re.compile(r"(\d+)\.(\d+)").match(channel_or_release)
        if match:
            self.channel = f"#art-release-{match[1]}-{match[2]}"
        else:
            raise ValueError(f"Invalid channel_or_release value: {channel_or_release}")

    async def say(self, message: str, thread_ts: Optional[str] = None):
        attachments = []
        if self.job_run_url:
            attachments.append({
                "title": f"Job: {self.job_name} <{self.job_run_url}|{self.job_run_name}>",
                "color": "#439FE0",
            })
        if self.dry_run:
            _LOGGER.warning("[DRY RUN] Would have sent slack message to %s: %s %s", self.channel, message, attachments)
            return {"message": {"ts": "fake"}}
        response = await self._client.chat_postMessage(channel=self.channel, text=message, thread_ts=thread_ts,
                                                       username=self.as_user, link_names=True, attachments=attachments,
                                                       icon_emoji=self.icon_emoji, reply_broadcast=False)
        return response.data
