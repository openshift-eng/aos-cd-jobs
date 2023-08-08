import logging
import sys
import unittest
import asyncio

from mock import MagicMock, AsyncMock, patch
from pyartcd.pipelines.check_bugs import CheckBugsPipeline, is_prerelease

LOGGER = logging.getLogger(__name__)
LOGGER.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(stream_handler)


class TestCheckBugsPipeline(unittest.IsolatedAsyncioTestCase):
    def test_invalid_channel_name(self):
        runtime = MagicMock()
        self.assertRaises(
            ValueError,
            CheckBugsPipeline, runtime, 'invalid-channel-name', []
        )

    def test_valid_channel_name(self):
        runtime = MagicMock()
        CheckBugsPipeline(runtime, '#valid-channel-name', [])


if __name__ == "__main__":
    unittest.main()
