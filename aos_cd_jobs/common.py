#!/usr/bin/env python
from os import getenv
from os.path import exists, join

from git import Repo

JOBS_DIRECTORY = 'jobs'

def initialize_repo():
    repo_dir = join(getenv('WORKSPACE'), 'aos-cd-jobs')
    if exists(repo_dir):
        return Repo(repo_dir)
    return Repo.clone_from('git@github.com:openshift/aos-cd-jobs.git', repo_dir)
