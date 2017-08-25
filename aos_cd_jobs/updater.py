#!/usr/bin/env python
from os import chdir, listdir, remove, rename, walk
from os.path import isdir, join, relpath
from shutil import rmtree

from aos_cd_jobs.common import JOBS_DIRECTORY, initialize_repo

def update_branches(repo):
    for job in list_jobs(repo):
        if job not in repo.branches:
            if job in repo.remotes['origin'].refs:
                repo.create_head(job, 'origin/{}'.format(job))
            else:
                repo.create_head(job, 'master')
        create_remote_branch(repo, job)

def list_jobs(repo):
    jobs = []
    jobs_directory = join(repo.working_dir, JOBS_DIRECTORY)
    for (dirpath, _, filenames) in walk(jobs_directory):
        if 'Jenkinsfile' in filenames:
            jobs.append(relpath(dirpath, jobs_directory))
    return jobs

def create_remote_branch(repo, name):
    branch = repo.branches[name]
    populate_branch(repo, branch)
    publish_branch(repo, name)

def populate_branch(repo, branch):
    branch.checkout()
    clean_file_tree(repo.working_dir)
    repo.git.checkout('master', '--', '.')
    create_job_file_tree(repo, branch)
    repo.git.add(all=True)
    if not branch.repo.index.diff(branch.commit):
        return
    repo.index.commit(
        'Auto-generated commit from {}'.format(
            repo.heads.master.commit.hexsha[:7]))

def clean_file_tree(directory):
    for f in listdir(directory):
        if f == '.git':
            continue
        if isdir(f):
            rmtree(f)
        else:
            remove(f)

def create_job_file_tree(repo, branch):
    job_directory = join(repo.working_dir, JOBS_DIRECTORY, branch.name)
    for f in listdir(job_directory):
        rename(join(job_directory, f), join(repo.working_dir, f))
    rmtree(join(repo.working_dir, JOBS_DIRECTORY))

def publish_branch(repo, name):
    repo.remotes.origin.push(name)

if __name__ == '__main__':
    repo = initialize_repo()
    chdir(repo.working_dir)
    update_branches(repo)
