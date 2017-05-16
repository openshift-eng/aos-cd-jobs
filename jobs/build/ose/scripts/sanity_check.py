#!/usr/bin/env python
from __future__ import print_function

import sys
import re

import git

def validate_commits(commits, out=sys.stderr):
    """
    Validate that the list of commits we are
    about to operate on meets our assumptions.

    :param commits: commits to check
    """

    # Validate commit messages.
    for commit in commits:
        validate_commit_message(commit, out)

    # Validate tito commits.
    validate_tito_commits(commits, out)

    # Validate all commits that will be carried.
    validate_carries(commits, out)

def validate_commit_message(commit, out=sys.stderr):
    drop_commit = commit.subject.startswith(git._DROP_PREFIX)
    carry_commit = commit.subject.startswith(git._CARRY_PREFIX)
    squash_commit = commit.subject.startswith(git._SQUASH_PREFIX)
    tito_commit = commit.subject.startswith(git._TITO_PREFIX)

    if not drop_commit and not carry_commit and not squash_commit and not tito_commit:
        print('Commit `{}` ({}) does not conform to naming requirements!'.format(commit.subject, commit.hash), file=out)
        exit(1)

    if carry_commit or squash_commit:
        prefix = git._CARRY_PREFIX
        if squash_commit:
           prefix = git._SQUASH_PREFIX

        subject = commit.subject[len(prefix):]
        match = re.match(r"\[.*\]", subject)
        if match is None or len(match.group(0)) < 3:
            print('Found a {} commit without a type: `{}` ({})'.format(prefix, commit.subject, commit.hash), file=out)
            exit(1)


def validate_tito_commits(commits, out=sys.stderr):
    tito_index = -1
    spec_index = -1
    for index, commit in enumerate(commits):
        if commit.subject.startswith(git._TITO_PREFIX):
            tito_index = index
        if commit.subject.startswith(git._SPEC_PREFIX):
            spec_index = index

    if tito_index < 0:
        print('No commit from `tito tag` found!', file=out)
        exit(1)

    if spec_index < 0:
        print('No carry commit for `.spec` file found!', file=out)
        exit(1)

    if tito_index < spec_index:
        print('Found the `tito tag` commit before the `.spec` file  commit!', file=out)
        exit(1)

def validate_carries(commits, out=sys.stderr):
    # Validate that CARRIES have a type.
    carry_types = filter_commits_by_prefix(commits, git._CARRY_PREFIX, out)

    # Validate that CARRY types are unique across all CARRIES.
    if len(carry_types) != len(set(carry_types)):
        print('Found more than one carry commit with the same type!', file=out)
        exit(1)

    # Validate that SQUASHES have a type.
    squash_types = filter_commits_by_prefix(commits, git._SQUASH_PREFIX, out)

    # Validate that all SQUASHES have a corresponding CARRY commit.
    if set(squash_types) & set(carry_types) != set(squash_types):
        print('Not all SQUASH commits correspond to a CARRY commit!', file=out)
        exit(1)

def filter_commits_by_prefix(commits, prefix, out):
    types = []
    for commit in commits:
        if commit.subject.startswith(prefix):
            subject = commit.subject[len(prefix):]
            # Commit message is already validated at this point.
            types.append(re.match(r"\[.*?\]", subject).group(0))

    return types

if __name__ == "__main__":
    rebase_path = sys.argv[1]
    commits = git.load_commits(rebase_path)

    validate_commits(commits)
