#!/usr/bin/env python
from os import getenv
from os.path import exists, join

from git import Repo

JOBS_DIRECTORY = 'jobs'


def initialize_repo():
    repo_dir = join(getenv('WORKSPACE'), 'aos-cd-jobs')
    if exists(repo_dir):
        print('Using current clone of aos-cd-jobs')
        return Repo(repo_dir)

    print('aos-cd-jobs not detected -- cloning a copy')
    return Repo.clone_from('git@github.com:openshift/aos-cd-jobs.git', repo_dir)

