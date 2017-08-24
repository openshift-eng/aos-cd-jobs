#!/usr/bin/env python
from unittest import TestCase, main
from mock import MagicMock, Mock, call, patch

from aos_cd_jobs.updater import create_job_file_tree, create_remote_branch, initialize_orphan_branch, list_jobs, publish_branch, populate_branch, update_branches

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
        directory = 'jobs/build/ose'
        create_job_file_tree('', 'jobs/build/ose')
        rename_mock.assert_has_calls((
            call('jobs/build/ose/Jenkinsfile', 'Jenkinsfile'),
            call('jobs/build/ose/README', 'README')))
        rmtree_mock.assert_called_once_with('jobs')

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('jobs0',))
    @patch('aos_cd_jobs.updater.create_remote_branch', lambda *_: None)
    def test_delete_local_branch(self):
        branch = Mock()
        branch.name = 'jobs0'
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.branches = {'jobs0': branch}
        update_branches(repo)
        self.assertTrue(branch.delete.called)

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('job0', 'job1'))
    @patch('aos_cd_jobs.updater.create_remote_branch')
    def test_update_branches(self, create_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.branches = {'job0': Mock(), 'job1': Mock()}
        update_branches(repo)
        create_mock.assert_has_calls((call(repo, 'job0'), call(repo, 'job1')))

    def test_initialize_branch(self):
        repo = Mock()
        name = 'job0'
        initialize_orphan_branch(repo, name)
        repo.heads.master.checkout.assert_called_once_with(orphan=name)

    @patch('aos_cd_jobs.updater.create_job_file_tree', lambda *_: None)
    def test_populate_branch(self):
        repo = MagicMock()
        repo.working_dir = 'aos-cd-jobs'
        repo.heads.master.commit.hexsha = '01234567abcdef'
        populate_branch(repo, 'job0')
        repo.git.add.assert_called_once_with(all=True)
        repo.index.commit.assert_called_once_with(
            'Auto-generated job branch from job0 from 0123456')

    def test_publish_branch(self):
        repo = Mock()
        name = 'job0'
        publish_branch(repo, name)
        repo.remotes.origin.push.assert_called_once_with(name, force=True)


if __name__ == '__main__':
    main()
