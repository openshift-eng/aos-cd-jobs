#!/usr/bin/env python
from os import getenv, listdir, rename, walk
from os.path import join, relpath
from shutil import rmtree

from git import Repo

from aos_cd_jobs.common import JOBS_DIRECTORY, initialize_repo

def update_branches(repo):
    for job in list_jobs(repo):
        if job in repo.branches:
            branch = repo.branches[job]
        else:
            branch = None
        if branch is not None:
            branch.delete()
        create_remote_branch(repo, job)

def list_jobs(repo):
    jobs = []
    jobs_directory = join(repo.working_dir, JOBS_DIRECTORY)
    for (dirpath, _, filenames) in walk(jobs_directory):
        if 'Jenkinsfile' in filenames:
            jobs.append(relpath(dirpath, jobs_directory))
    return jobs

def create_remote_branch(repo, name):
    branch = repo.heads.master.checkout(orphan=name)
    directory = join(repo.working_dir, JOBS_DIRECTORY, name)
    create_job_file_tree(repo.working_dir, directory)
    repo.index.remove(repo.index.entries.values())
    repo.index.add([f for f in listdir(repo.working_dir) if f != '.git'])
    repo.index.commit(
        'Auto-generated job branch from {} from {}'.format(
            name, repo.heads.master.commit.hexsha[:7]))
    repo.remotes.origin.push(name, force=True)

def create_job_file_tree(repo_directory, job_directory):
    for f in listdir(job_directory):
        rename(join(job_directory, f), join(repo_directory, f))
    rmtree(join(repo_directory, JOBS_DIRECTORY))

if __name__ == '__main__':
    repo = initialize_repo()
    update_branches(repo)
