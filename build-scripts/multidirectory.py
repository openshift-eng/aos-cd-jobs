#!/usr/bin/env python
import os
import shutil
import subprocess
import sys

def remove_branches(remote):
    branches = subprocess.check_output([
        'git', 'branch', '--list', '--remotes', '--no-merged', 'HEAD',
        remote + '/*'])
    for branch in [x[len(remote) + 1:] for x in branches.split()]:
        if not os.path.exists(os.path.join('jobs', branch, 'Jenkinsfile')):
            subprocess.check_call([
                'git', 'push', '--quiet', '--delete', remote, branch])

def create_or_update_branches(remote):
    if not os.path.exists('jobs/'):
        return
    msg = 'Auto-generated job branch from {{}} from {}'.format(
        subprocess.check_output(['git', 'log', '-n', '1', '--pretty=%h']))
    jobs = [d for (d, _, files) in os.walk('jobs/') if 'Jenkinsfile' in files]
    for job in jobs:
        branch = job[len('jobs/'):]
        if not subprocess.call([
                'git', 'rev-parse', '--verify', '--quiet',
                'refs/heads/' + branch]):
            subprocess.check_call(
                ['git', 'branch', '--delete', '--force', branch])
        subprocess.check_call(
            ['git', 'checkout', '--quiet', '--orphan', branch, 'master'])
        for file in os.listdir(job):
            os.rename(os.path.join(job, file), file)
        shutil.rmtree(job)
        subprocess.check_call(['git', 'add', '.'])
        subprocess.check_call(
            ['git', 'commit', '--quiet', '--message', msg.format(branch)])
        subprocess.check_call(
            ['git', 'push', '--quiet', remote, '--force', branch])

if __name__ == '__main__':
    remote = sys.argv[1] if len(sys.argv) > 1 else 'origin'
    subprocess.check_call(['git', 'checkout', '--quiet', 'master'])
    remove_branches(remote)
    create_or_update_branches(remote)
