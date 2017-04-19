#!/usr/bin/env python
from os.path import join, exists

from aos_cd_jobs.common import JOBS_DIRECTORY, initialize_repo


def prunable_remote_refs(repo):
    candidates = []
    for ref in repo.remotes.origin.refs:
        if not (ref.remote_head == 'HEAD' or ref.remote_head == 'master'):
            candidates.append(ref)
    return candidates


def remote_ref_needs_pruning(ref):
    return not exists(jenkinsfile_for_ref(ref))

def jenkinsfile_for_ref(ref):
    return join(
        ref.repo.working_dir,
        JOBS_DIRECTORY,
        ref.remote_head,
        'Jenkinsfile'
    )

def prune_remote_ref(ref):
    ref.repo.remotes[ref.remote_name].push(':' + ref.remote_head)


def prune_remote_refs(repo):
    for ref in prunable_remote_refs(repo):
        if remote_ref_needs_pruning(ref):
            prune_remote_ref(ref)

if __name__ == '__main__':
    repo = initialize_repo()
    prune_remote_refs(repo)
