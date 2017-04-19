#!/usr/bin/env python
from unittest import TestCase, main
from mock import MagicMock, Mock, patch

from aos_cd_jobs.pruner import jenkinsfile_for_ref, prunable_remote_refs, prune_remote_refs

class TestPruneMethods(TestCase):
    def test_jenkinsfile_for_ref(self):
        """ Jenksinsfile should be under ref path from repo root """
        ref = MagicMock()
        ref.repo.working_dir = 'base'
        ref.remote_head = 'path'

        self.assertEqual(jenkinsfile_for_ref(ref), 'base/jobs/path/Jenkinsfile')

    def test_prunable_remote_refs_exclude_head(self):
        """ HEAD should not be considered prunable """
        ref = MagicMock()
        ref.remote_head = 'HEAD'
        repo = MagicMock()
        repo.remotes.origin.refs = [ref]

        self.assertEqual(prunable_remote_refs(repo), [])

    def test_prunable_remote_refs_exclude_master(self):
        """ master should not be considered prunable """
        ref = MagicMock()
        ref.remote_head = 'master'
        repo = MagicMock()
        repo.remotes.origin.refs = [ref]

        self.assertEqual(prunable_remote_refs(repo), [])

    def test_prunable_remote_refs_contain_rest(self):
        """ normal refs should be considered prunable """
        repo = MagicMock()
        repo.remotes.origin.refs = [MagicMock()] * 10

        self.assertEqual(prunable_remote_refs(repo), repo.remotes.origin.refs)

    @patch('aos_cd_jobs.pruner.remote_ref_needs_pruning', Mock(return_value=True))
    @patch('aos_cd_jobs.pruner.prunable_remote_refs', Mock(return_value=[MagicMock()]))
    @patch('aos_cd_jobs.pruner.prune_remote_ref')
    def test_prune_remote_refs_positive(self, prune_remote_ref_mock):
        """ refs that need pruning should be pruned """
        prune_remote_refs(MagicMock())

        self.assertTrue(prune_remote_ref_mock.called)

    @patch('aos_cd_jobs.pruner.remote_ref_needs_pruning', Mock(return_value=False))
    @patch('aos_cd_jobs.pruner.prunable_remote_refs', Mock(return_value=[MagicMock()]))
    @patch('aos_cd_jobs.pruner.prune_remote_ref')
    def test_prune_remote_refs_negative(self, prune_remote_ref_mock):
        """ refs that do not need pruning should not be pruned """
        prune_remote_refs(MagicMock())

        self.assertFalse(prune_remote_ref_mock.called)


if __name__ == '__main__':
    main()
