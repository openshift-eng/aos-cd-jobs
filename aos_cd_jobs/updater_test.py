#!/usr/bin/env python
from unittest import TestCase, main
from mock import MagicMock, Mock, call, patch

from aos_cd_jobs.updater import create_job_file_tree, create_remote_branch, list_jobs, publish_branch, populate_branch, update_branches

class TestUpdateMethods(TestCase):
    @patch('aos_cd_jobs.updater.walk')
    def test_list_jobs_positive(self, walk_mock):
        walk_mock.return_value = (('dir/jobs/job0', None, ['Jenkinsfile']),)
        repo = Mock()
        repo.working_dir = 'dir'
        self.assertEqual(list_jobs(repo), ['job0'])

    @patch('aos_cd_jobs.updater.walk')
    def test_list_jobs_negative(self, walk_mock):
        walk_mock.return_value = (('dir/jobs/notajob', None, ['']),)
        repo = Mock()
        repo.working_dir = 'dir'
        self.assertEqual(list_jobs(repo), [])

    @patch('aos_cd_jobs.updater.listdir', lambda _: ('Jenkinsfile', 'README'))
    @patch('aos_cd_jobs.updater.rename')
    @patch('aos_cd_jobs.updater.rmtree')
    def test_create_job_file_tree(self, rmtree_mock, rename_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        branch = Mock()
        branch.name = 'build/ose'
        create_job_file_tree(repo, branch)
        rename_mock.assert_has_calls((
            call(
                '/tmp/aos-cd-jobs/jobs/build/ose/Jenkinsfile',
                '/tmp/aos-cd-jobs/Jenkinsfile'),
            call(
                '/tmp/aos-cd-jobs/jobs/build/ose/README',
                '/tmp/aos-cd-jobs/README')))
        rmtree_mock.assert_called_once_with('/tmp/aos-cd-jobs/jobs')

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('job0', 'job1'))
    @patch('aos_cd_jobs.updater.create_remote_branch')
    def test_update_branches(self, create_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.branches = {'job0': Mock(), 'job1': Mock()}
        update_branches(repo)
        create_mock.assert_has_calls((call(repo, 'job0'), call(repo, 'job1')))

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('job0',))
    @patch('aos_cd_jobs.updater.create_remote_branch')
    def test_update_branches_remote(self, create_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.branches = []
        repo.remotes = MagicMock()
        repo.remotes['origin'].refs = {'job0': Mock()}
        update_branches(repo)
        repo.create_head.assert_has_calls((call('job0', 'origin/job0'),))
        create_mock.assert_has_calls((call(repo, 'job0'),))

    @patch('aos_cd_jobs.updater.create_remote_branch', lambda *_: None)
    @patch('aos_cd_jobs.updater.list_jobs')
    def test_update_branches_new(self, list_jobs_mock):
        list_jobs_mock.return_value = ['job0']
        repo = Mock()
        repo.branches = []
        repo.remotes = MagicMock()
        repo.remotes['origin'].refs = []
        update_branches(repo)
        repo.create_head.assert_called_once_with('job0', 'master')

    @patch('aos_cd_jobs.updater.clean_file_tree', lambda *_: None)
    @patch('aos_cd_jobs.updater.create_job_file_tree', lambda *_: None)
    def test_populate_branch(self):
        repo = MagicMock()
        repo.heads.master.commit.hexsha = '01234567abcdef'
        branch = Mock()
        populate_branch(repo, branch)
        repo.git.add.assert_called_once_with(all=True)
        repo.index.commit.assert_called_once_with(
            'Auto-generated commit from 0123456')

    def test_publish_branch(self):
        repo = Mock()
        name = 'job0'
        publish_branch(repo, name)
        repo.remotes.origin.push.assert_called_once_with(name)


if __name__ == '__main__':
    main()
