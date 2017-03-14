#!/usr/bin/env python
from __future__ import print_function

import sys

_DROP_PREFIX = '[DROP]'
_SQUASH_PREFIX = '[SQUASH]'
_CARRY_PREFIX = '[CARRY]'
_SPEC_SUBJECT = _CARRY_PREFIX + '[BUILD] Specfile updates'
_TITO_PREFIX = 'Automatic commit of package'


class Action(object):
    pick    = 'pick'    # use the commit as-is
    reword  = 'reword'  # edit the subject
    edit    = 'edit'    # edit the content
    squash  = 'squash'  # meld into previous
    fixup   = 'fixup'   # meld but drop the subject
    execute = 'exec'    # run a shell command
    drop    = 'drop'    # remove the commit


class Commit(object):
    """
    An entry in an interactive git rebase
    file, containing the action, hash and
    subject.
    """

    def __init__(self, action, hash, subject):
        self.action = action
        self.hash = hash
        self.subject = subject

    def __str__(self):
        return '{} {} {}'.format(self.action, self.hash, self.subject)

def load_commits(rebase_path):
    """
    Load the list of commits we need to deal
    with from a file generated from an inter-
    active `git rebase`.

    :param rebase_path: path to the rebase file
    :return: list of commits
    """
    commits = []
    with open(rebase_path) as rebase_file:
        for line in rebase_file:
            line = line.strip('\n')
            # when we first load a rebase file, all
            # the commits are in the 'pick' state
            if line.startswith(Action.pick):
                commits.append(Commit(
                    action=Action.pick,
                    hash=line[5:12],
                    subject=line[13:]
                ))

    return commits


def dump_commits(rebase_path, commits):
    """
    Write the list of commits to the rebase
    file for `git rebase` to operate on.

    :param rebase_path: path to the rebase file
    :param commits: commits to write
    """
    with open(rebase_path, 'w') as rebase_file:
        for commit in commits:
            rebase_file.write(str(commit))
            rebase_file.write('\n')


def validate_commits(commits):
    """
    Validate that the list of commits we are
    about to operate on meets our assumptions.

    :param commits: commits to check
    """
    tito_index = -1
    spec_index = -1
    for index, commit in enumerate(commits):
        drop_commit = commit.subject.startswith(_DROP_PREFIX)
        carry_commit = commit.subject.startswith(_CARRY_PREFIX)
        squash_commit = commit.subject.startswith(_SQUASH_PREFIX)
        tito_commit = commit.subject.startswith(_TITO_PREFIX)

        if not drop_commit and not carry_commit and not squash_commit and not tito_commit:
            print('Commit `{}` ({}) invalid!'.format(commit.subject, commit.hash))
            exit(1)

        if tito_commit:
            tito_index = index

        if commit.subject == _SPEC_SUBJECT:
            spec_index = index

    if tito_index < 0:
        print('No commit from `tito tag` found!')
        exit(1)

    if spec_index < 0:
        print('No carry commit for `.spec` file found!')
        exit(1)

    if tito_index < spec_index:
        print('Found the `tito tag` commit before the `.spec` file  commit!')
        exit(1)


def remove_drop_commits(commits):
    """
    Remove commits labelled for removal with
    the '[DROP]' prefix in their commit subject.

    :param commits: commits to prune
    :return: pruned commits
    """
    for commit in commits:
        if commit.subject.startswith(_DROP_PREFIX):
            commit.action = Action.drop

    return commits

def commit_index(commits, filter):
    """
    Find the index of a commit you know exists
    in the list of commits by passing a filter
    function that matches it. The first match
    is returned.

    :param commits: commits to search
    :param filter: filter function taking commit
    :return: first match
    """
    for index, commit in enumerate(commits):
        if filter(commit):
            return index

def squash_tito_commits(commits):
    """
    Squash the auto-generated commit from the
    last `tito tag` with the carry commit for
    the `.spec` file.

    :param commits: commits to consider
    :return: updated commits
    """
    tito_index = commit_index(commits, lambda c: c.subject.startswith(_TITO_PREFIX))
    spec_index = commit_index(commits, lambda c: c.subject == _SPEC_SUBJECT)

    tito_commit = commits.pop(tito_index)
    tito_commit.action = Action.fixup
    commits.insert(spec_index + 1, tito_commit)

    return commits


def squash_named_commits(commits):
    """
    Search through the list of commits and re-order
    any commits marked for squash. We need to make
    sure we squash the commits in the same order
    that they were originally committed in so that
    we can ensure they apply cleanly on top of each
    other.

    :param commits: commits to search through
    :return: updated commits
    """
    carry_commits = []
    for commit in commits:
        if commit.subject.startswith(_CARRY_PREFIX):
            carry_commits.append(commit)

    for carry_commit in carry_commits:
        squash_subject = _SQUASH_PREFIX + carry_commit.subject
        carry_commit_index = commits.index(carry_commit)
        squash_commit_indicies = []
        for index, commit in enumerate(commits):
            if commit.subject == squash_subject:
                squash_commit_indicies.append(index)

        for index, squash_commit_index in enumerate(squash_commit_indicies):
            squash_commit = commits.pop(squash_commit_index)
            squash_commit.action = Action.fixup
            commits.insert(carry_commit_index + index + 1, squash_commit)

    return commits

rebase_path = sys.argv[1]
commits = load_commits(rebase_path)

validate_commits(commits)
commits = remove_drop_commits(commits)
commits = squash_tito_commits(commits)
commits = squash_named_commits(commits)

dump_commits(rebase_path, commits)
