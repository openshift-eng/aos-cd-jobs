from unittest import TestCase
from mock import Mock, AsyncMock, patch, ANY
from asyncio import get_event_loop

from mock.mock import MagicMock

from pyartcd.pipelines.tarball_sources import TarballSourcesPipeline


class TestTarballSourcesPipeline(TestCase):
    @patch("pyartcd.exectools.cmd_gather_async")
    def test_create_tarball_sources(self, cmd_gather_async: Mock):
        cmd_gather_async.return_value = (0, """
Created tarball source /mnt/nfs/home/jenkins/yuxzhu/OSE-4.6-RHEL-8/84693/release/logging-fluentd-container-v4.6.0-202111191944.p0.gf73a1dd.assembly.stream.tar.gz.


All tarball sources are successfully created.

To send all tarball sources to rcm-guest, run:

    rsync -avz --no-perms --no-owner --no-group /mnt/nfs/home/jenkins/yuxzhu/ ocp-build@rcm-guest.app.eng.bos.redhat.com:/mnt/rcm-guest/ocp-client-handoff/

Then notify RCM (https://projects.engineering.redhat.com/projects/RCM/issues) that the following tarball sources have been uploaded to rcm-guest:

OSE-4.6-RHEL-8/84693/release/logging-fluentd-container-v4.6.0-202111191944.p0.gf73a1dd.assembly.stream.tar.gz
        """, "")
        expected = ['OSE-4.6-RHEL-8/84693/release/logging-fluentd-container-v4.6.0-202111191944.p0.gf73a1dd.assembly.stream.tar.gz']
        pipeline = TarballSourcesPipeline(MagicMock(dry_run=False), "fake-group-4.10", "fake-assembly", ["fake-component"], [])
        actual = get_event_loop().run_until_complete(pipeline._create_tarball_sources([10000, 10001], "fake-working/sources"))
        self.assertEqual(actual, expected)

    @patch("pyartcd.exectools.cmd_assert_async")
    def test_copy_to_rcm_guest(self, cmd_assert_async: AsyncMock):
        cmd_assert_async.return_value = (0, "whatever", "whatever")
        pipeline = TarballSourcesPipeline(MagicMock(dry_run=False), "fake-group-4.10", "fake-assembly", ["fake-component"], [])
        get_event_loop().run_until_complete(pipeline._copy_to_rcm_guest("fake-working/sources"))
        cmd_assert_async.assert_awaited_once_with(["rsync", "-avz", "--no-perms", "--no-owner", "--no-group", "fake-working/sources", ANY])

    def test_create_jira(self):
        runtime = MagicMock(dry_run=False)
        pipeline = TarballSourcesPipeline(runtime, "fake-group-4.10", "fake-assembly", ["fake-component"], [])
        jira_client = pipeline._jira_client
        actual = pipeline._create_jira([10000], ["source-1.tar.gz", "source-2.tar.gz"])
        jira_client.create_issue.assert_called_once_with("CLOUDDST", "Ticket", ANY, ANY)
        self.assertEqual(actual, jira_client.create_issue.return_value)

    @patch("pyartcd.util.load_group_config")
    def test_run(self, load_group_config: AsyncMock):
        runtime = MagicMock(dry_run=False)
        load_group_config.return_value = {"advisories": {"extras": 10000, "image": 10001}}
        pipeline = TarballSourcesPipeline(runtime, "fake-group-4.10", "fake-assembly", ["fake-component"], [])
        pipeline._create_tarball_sources = AsyncMock(return_value=["source-1.tar.gz", "source-2.tar.gz"])
        pipeline._copy_to_rcm_guest = AsyncMock()
        pipeline._create_jira = MagicMock(return_value=MagicMock(key="FAKE-123"))
        get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("fake-group-4.10", "fake-assembly", ANY)
        pipeline._create_tarball_sources.assert_awaited_once_with([10000, 10001], ANY)
        pipeline._copy_to_rcm_guest.assert_awaited_once_with(ANY)
        pipeline._create_jira.assert_called_once_with([10000, 10001], ["source-1.tar.gz", "source-2.tar.gz"])
