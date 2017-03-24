#!/usr/bin/env python
import os
import shutil
import subprocess
import sys

def remove_branches(remote):
    branch_refs = subprocess.check_output([
        'git', 'branch', '--list', '--remotes', '--no-merged', 'HEAD',
        remote + '/*'])
    branch_names = [ref[len(remote) + 1:] for ref in branch_refs.split()]
    for branch in branch_names:
        prune_branch(branch)

def create_or_update_branches(remote):
    if not os.path.exists('jobs/'):
        return
    job_directories = \
        [d for (d, _, files) in os.walk('jobs/') if 'Jenkinsfile' in files]
    for job in job_directories:
        branch = job[len('jobs/'):]
        create_or_update_branch(branch)

def prune_branch(branch):
    if not jenkinsfile_exists(branch):
        delete_remote_branch(branch)

def jenkinsfile_exists(branch):
    return os.path.exists(os.path.join('jobs', branch, 'Jenkinsfile'))

def delete_remote_branch(branch):
    subprocess.check_call([
        'git', 'push', '--quiet', '--delete', remote, branch])

def create_or_update_branch(branch):
    if branch_exists_locally(branch):
        delete_local_branch(branch)
    create_remote_branch(branch)

def branch_exists_locally(branch):
    return not subprocess.call(
        ['git', 'rev-parse', '--verify', '--quiet', 'refs/heads/' + branch])

def delete_local_branch(branch):
    subprocess.check_call(['git', 'branch', '--delete', '--force', branch])

def create_remote_branch(branch):
    subprocess.check_call(
        ['git', 'checkout', '--quiet', '--orphan', branch, 'master'])
    directory = os.path.join('jobs', branch)
    for file in os.listdir(directory):
        os.rename(os.path.join(directory, file), file)
    shutil.rmtree(directory)
    subprocess.check_call(['git', 'add', '.'])
    msg = 'Auto-generated job branch from {} from {}'.format(
        branch,
        subprocess.check_output(
            ['git', 'log', '-n', '1', '--pretty=%h', 'master']))
    subprocess.check_call(['git', 'commit', '--quiet', '--message', msg])
    subprocess.check_call(
        ['git', 'push', '--quiet', remote, '--force', branch])

if __name__ == '__main__':
    remote = sys.argv[1] if len(sys.argv) > 1 else 'origin'
    subprocess.check_call(['git', 'checkout', '--quiet', 'master'])
    remove_branches(remote)
    create_or_update_branches(remote)
