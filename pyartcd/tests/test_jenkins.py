import unittest
import os
from mock import mock
from pyartcd import jenkins


class TestJenkinsStartBuild(unittest.TestCase):
    @mock.patch("pyartcd.jenkins.init_jenkins")
    @mock.patch("pyartcd.jenkins.jenkins_client")
    def test_start_build_dont_block(self, mock_client, mock_init_jenkins):
        job_name = "foo"
        params = {"param1": "value1", "param2": "value2"}
        mock_job = mock.MagicMock()
        mock_client.get_job.return_value = mock_job
        jenkins.start_build(job_name, params, block_until_building=False)

        mock_init_jenkins.assert_called_once()
        mock_client.get_job.assert_called_once_with(job_name)
        mock_job.invoke.assert_called_once_with(build_params=params)

    @mock.patch("pyartcd.jenkins.Build")
    @mock.patch("pyartcd.jenkins.init_jenkins")
    @mock.patch("pyartcd.jenkins.jenkins_client")
    def test_start_build_block_until_building(self, mock_client, mock_init_jenkins, mock_build):
        job_name = "foo"
        params = {"param1": "value1", "param2": "value2"}
        delay = 10
        mock_client.get_job.return_value = mock_job = mock.MagicMock()
        mock_job.invoke.return_value = mock_queue_item = mock.MagicMock()
        mock_queue_item.poll.return_value = {'executable': {'number': 1}, 'task': {'url': 'folder/foo/'}}
        triggered_url = 'folder/foo/1'
        os.environ['BUILD_URL'] = 'folder/bar/1'
        os.environ['JOB_NAME'] = 'bar'

        result = jenkins.start_build(job_name, params, block_until_building=True, watch_building_delay=delay)
        self.assertEqual(result, None)

        mock_init_jenkins.assert_called_once()
        mock_client.get_job.assert_called_once_with(job_name)
        mock_job.invoke.assert_called_once_with(build_params=params)
        mock_queue_item.poll.assert_called_once()
        mock_build.assert_called_once_with(url=triggered_url, buildno=1, job=mock_job)

    @mock.patch("pyartcd.jenkins.Build")
    @mock.patch("pyartcd.jenkins.init_jenkins")
    @mock.patch("pyartcd.jenkins.jenkins_client")
    def test_start_build_block_until_complete(self, mock_client, mock_init_jenkins, mock_build):
        job_name = "foo"
        params = {"param1": "value1", "param2": "value2"}
        delay = 10
        mock_client.get_job.return_value = mock_job = mock.MagicMock()
        mock_job.invoke.return_value = mock_queue_item = mock.MagicMock()
        mock_queue_item.poll.return_value = {'executable': {'number': 1}, 'task': {'url': 'folder/foo/'}}
        triggered_url = 'folder/foo/1'
        os.environ['BUILD_URL'] = 'folder/bar/1'
        os.environ['JOB_NAME'] = 'bar'
        mock_build.return_value.poll.return_value = {'result': 'SUCCESS'}

        result = jenkins.start_build(job_name, params, block_until_building=True,
                                     block_until_complete=True, watch_building_delay=delay)
        self.assertEqual(result, 'SUCCESS')

        mock_init_jenkins.assert_called_once()
        mock_client.get_job.assert_called_once_with(job_name)
        mock_job.invoke.assert_called_once_with(build_params=params)
        mock_queue_item.poll.assert_called_once()
        mock_build.assert_called_once_with(url=triggered_url, buildno=1, job=mock_job)
