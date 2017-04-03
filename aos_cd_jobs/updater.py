#!/usr/bin/env python
from os import getenv, listdir, rename, walk
from os.path import join
from shutil import rmtree

from git import Repo

def initialize_repo():
    repo_dir = join(getenv('WORKSPACE'), 'aos-cd-jobs')
    return Repo.clone_from('git@github.com:openshift/aos-cd-jobs.git', repo_dir)

def update_branches(repo):
    jobs_directory = join(repo.working_dir, 'jobs')
    for job in list_jobs(jobs_directory, walk(jobs_directory)):
        branch = get_branch_by_name(repo.branches, job)
        if branch is not None:
            branch.delete()
        create_remote_branch(repo, job)

def list_jobs(directory, walker):
    return (
        name[len(directory) + 1:]
        for (name, _, files) in walker
        if 'Jenkinsfile' in files
    )

def get_branch_by_name(branches, name):
    return next((b for b in branches if b.name == name), None)

def create_remote_branch(repo, name):
    branch = repo.active_branch.checkout(orphan=name)
    directory = join(repo.working_dir, 'jobs', name)
    create_branch(directory, listdir(directory))
    repo.index.add(['.'])
    repo.index.commit(
        'Auto-generated job branch from {} from {}'.format(
            name, repo.heads.master.commit.hexsha[:7]))
    repo.remotes.origin.push(name, force=True)

def create_branch(directory, files):
    for file in files:
        rename(join(directory, file), file)
    rmtree(directory)

if __name__ == '__main__':
    repo = initialize_repo()
    update_branches(repo)
