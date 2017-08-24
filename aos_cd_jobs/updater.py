#!/usr/bin/env python
from os import listdir, rename, walk
from os.path import join, relpath
from shutil import rmtree

from aos_cd_jobs.common import JOBS_DIRECTORY, initialize_repo

def update_branches(repo):
    for job in list_jobs(repo):
        if job in repo.branches:
            repo.branches[job].delete()
        create_remote_branch(repo, job)

def list_jobs(repo):
    jobs = []
    jobs_directory = join(repo.working_dir, JOBS_DIRECTORY)
    for (dirpath, _, filenames) in walk(jobs_directory):
        if 'Jenkinsfile' in filenames:
            jobs.append(relpath(dirpath, jobs_directory))
    return jobs

def create_remote_branch(repo, name):
    initialize_orphan_branch(repo, name)
    populate_branch(repo, name)
    publish_branch(repo, name)

def initialize_orphan_branch(repo, name):
    repo.heads.master.checkout(orphan=name)

def populate_branch(repo, name):
    directory = join(repo.working_dir, JOBS_DIRECTORY, name)
    create_job_file_tree(repo.working_dir, directory)
    repo.git.add(all=True)
    repo.index.commit(
        'Auto-generated job branch from {} from {}'.format(
            name, repo.heads.master.commit.hexsha[:7]))

def create_job_file_tree(repo_directory, job_directory):
    for f in listdir(job_directory):
        rename(join(job_directory, f), join(repo_directory, f))
    rmtree(join(repo_directory, JOBS_DIRECTORY))

def publish_branch(repo, name):
    repo.remotes.origin.push(name, force=True)

if __name__ == '__main__':
    repo = initialize_repo()
    update_branches(repo)
