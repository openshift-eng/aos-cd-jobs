#!/usr/bin/env python
from os import getenv, listdir, rename, walk
from os.path import join
from shutil import rmtree

from git import Repo

from aos_cd_jobs.common import JOBS_DIRECTORY, initialize_repo

def update_branches(repo):
    for job in list_jobs(repo):
        branch = get_branch_by_name(repo.branches, job)
        if branch is not None:
            branch.delete()
        create_remote_branch(repo, job)

def list_jobs(repo):
    jobs = []
    jobs_directory = join(repo.working_dir, JOBS_DIRECTORY)
    for (dirpath, _, filenames) in walk(jobs_directory):
        if 'Jenkinsfile' in filenames:
            jobs.append(dirpath[len(jobs_directory) + 1:])
    return jobs

def get_branch_by_name(branches, name):
    if name in branches:
        return branches[name]

def create_remote_branch(repo, name):
    branch = repo.active_branch.checkout(orphan=name)
    directory = join(repo.working_dir, JOBS_DIRECTORY, name)
    create_job_file_tree(directory, listdir(directory))
    repo.index.add(['.'])
    repo.index.commit(
        'Auto-generated job branch from {} from {}'.format(
            name, repo.heads.master.commit.hexsha[:7]))
    repo.remotes.origin.push(name, force=True)

def create_job_file_tree(directory, files):
    for file in files:
        rename(join(directory, file), file)
    rmtree(directory)

if __name__ == '__main__':
    repo = initialize_repo()
    update_branches(repo)
