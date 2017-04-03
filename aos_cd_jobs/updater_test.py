#!/usr/bin/env python
from unittest import TestCase, main
from mock import Mock, call, patch

from aos_cd_jobs.updater import create_branch, create_remote_branch, get_branch_by_name, list_jobs, update_branches

class TestUpdateMethods(TestCase):
    def test_list_jobs(self):
        walker = (
            ('dir/job0', None, ['Jenkinsfile']),
            ('dir/notajob', None, ['']),
            ('dir/job1', None, ['Jenkinsfile']),
        )
        self.assertEqual(tuple(list_jobs('dir', walker)), ('job0', 'job1'))

    def test_get_branch_by_name(self):
        branches = (Mock(), Mock())
        branches[0].name = 'branch0'
        branches[1].name = 'branch1'
        self.assertEqual(get_branch_by_name(branches, 'branch0'), branches[0])
        self.assertEqual(get_branch_by_name(branches, 'branch1'), branches[1])
        self.assertIsNone(get_branch_by_name(branches, 'branch2'))

    @patch('aos_cd_jobs.updater.rename')
    @patch('aos_cd_jobs.updater.rmtree')
    def test_create_branch(self, rmtree_mock, rename_mock):
        directory = 'jobs/build/ose'
        create_branch(directory, ('Jenkinsfile', 'README'))
        rename_mock.assert_has_calls((
            call('jobs/build/ose/Jenkinsfile', 'Jenkinsfile'),
            call('jobs/build/ose/README', 'README')))
        rmtree_mock.assert_called_once_with(directory)

    @patch('aos_cd_jobs.updater.listdir', lambda *_: ())
    @patch('aos_cd_jobs.updater.create_branch')
    def test_create_remote_branch(self, create_mock):
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.heads.master.commit.hexsha = '0123456789abcdef'
        create_remote_branch(repo, 'job')
        repo.active_branch.checkout.assert_called_once_with(orphan='job')
        create_mock.assert_called_once_with('/tmp/aos-cd-jobs/jobs/job', ())
        repo.index.add.assert_called_once_with(['.'])
        repo.index.commit.assert_called_once_with(
            'Auto-generated job branch from job from 0123456')
        repo.remotes.origin.push.assert_called_once_with('job', force=True)

    @patch('aos_cd_jobs.updater.list_jobs', lambda *_: ('jobs0',))
    @patch('aos_cd_jobs.updater.create_remote_branch', lambda *_: None)
    def test_delete_local_branch(self):
        branch = Mock()
        branch.name = 'jobs0'
        repo = Mock()
        repo.working_dir = '/tmp/aos-cd-jobs'
        repo.branches = (branch,)
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
