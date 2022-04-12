import logging
import sys
import unittest
import asyncio

from mock import MagicMock, AsyncMock, patch
from pyartcd.pipelines.check_bugs import CheckBugsPipeline

LOGGER = logging.getLogger(__name__)
LOGGER.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(stream_handler)


class TestCheckBugsPipeline(unittest.TestCase):
    def test_invalid_channel_name(self):
        runtime = MagicMock()
        self.assertRaises(
            ValueError,
            CheckBugsPipeline, runtime, 'invalid-channel-name', [], []
        )

    def test_valid_channel_name(self):
        runtime = MagicMock()
        CheckBugsPipeline(runtime, '#valid-channel-name', [], [])

    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline.initialize_slack_client", return_value=None)
    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline._slack_report", return_value=None)
    def test_find_blockers(self, *args):
        # A bogus bug has been created for 4.5:
        # https://bugzilla.redhat.com/show_bug.cgi?id=2069763
        runtime = AsyncMock()
        runtime.logger = LOGGER
        pipeline = CheckBugsPipeline(runtime, '#test', ['4.5'], ['4.6'])
        asyncio.get_event_loop().run_until_complete(pipeline.run())
        self.assertEqual(len(pipeline.blockers), 1)

    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline.initialize_slack_client", return_value=None)
    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline._slack_report", return_value=None)
    def test_next_is_prerelease(self, *args):
        runtime = AsyncMock()
        runtime.logger = LOGGER
        pipeline = CheckBugsPipeline(runtime, '#test', [], ['4.11'])
        self.assertTrue(pipeline._next_is_prerelease('4.10'))

    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline.initialize_slack_client", return_value=None)
    @patch("pyartcd.pipelines.check_bugs.CheckBugsPipeline._slack_report", return_value=None)
    def test_check_applicable_versions(self, *args):
        runtime = AsyncMock()
        runtime.logger = LOGGER

        versions = [
            '3.11',
            '4.6',
            '4.7',
            '4.8',
            '4.9',
            '4.10'
        ]
        versions.sort()

        # All OCP versions defined above are applicable
        pipeline = CheckBugsPipeline(runtime, '#test', versions, [])
        asyncio.get_event_loop().run_until_complete(pipeline._check_applicable_versions())
        pipeline.applicable_versions.sort()
        self.assertEqual(versions, pipeline.applicable_versions)

        # Add 4.11, currently (Mar 30, 2022) not in GA
        pipeline.versions.append('4.11')
        asyncio.get_event_loop().run_until_complete(pipeline._check_applicable_versions())
        self.assertNotIn('4.11', pipeline.applicable_versions)
        

if __name__ == "__main__":
    unittest.main()
