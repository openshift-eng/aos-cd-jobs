#!/usr/bin/env python
from unittest import TestCase, main
from mock import Mock, call, patch

from aos_cd_jobs.updater import create_job_file_tree, create_remote_branch, get_branch_by_name, list_jobs, update_branches

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

    def test_get_branch_by_name_positive(self):
        branches = {'branch0': 'branch0'}
        self.assertEqual(get_branch_by_name(branches, 'branch0'), 'branch0')

    def test_get_branch_by_name_negative(self):
        branches = {'branch0': 'branch0'}
        self.assertIsNone(get_branch_by_name(branches, 'branch1'))

    @patch('aos_cd_jobs.updater.rename')
    @patch('aos_cd_jobs.updater.rmtree')
    def test_create_job_file_tree(self, rmtree_mock, rename_mock):
        directory = 'jobs/build/ose'
        create_job_file_tree(directory, ('Jenkinsfile', 'README'))
        rename_mock.assert_has_calls((
            call('jobs/build/ose/Jenkinsfile', 'Jenkinsfile'),
            call('jobs/build/ose/README', 'README')))
        rmtree_mock.assert_called_once_with(directory)

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

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('jobs0', 'job1'))
    @patch('aos_cd_jobs.updater.get_branch_by_name', lambda *_: None)
    @patch('aos_cd_jobs.updater.create_remote_branch')
    def test_update_branches(self, create_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        update_branches(repo)
        create_mock.assert_has_calls((call(repo, 'jobs0'), call(repo, 'job1')))


if __name__ == '__main__':
    main()
