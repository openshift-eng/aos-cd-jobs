#!/usr/bin/env python
from __future__ import print_function

import sys
import git
import re

def validate_commits(commits):
    """
    Validate that the list of commits we are
    about to operate on meets our assumptions.

    :param commits: commits to check
    """
    tito_index = -1
    spec_index = -1
    for index, commit in enumerate(commits):
        drop_commit = commit.subject.startswith(git._DROP_PREFIX)
        carry_commit = commit.subject.startswith(git._CARRY_PREFIX)
        squash_commit = commit.subject.startswith(git._SQUASH_PREFIX)
        tito_commit = commit.subject.startswith(git._TITO_PREFIX)

        if not drop_commit and not carry_commit and not squash_commit and not tito_commit:
            print('Commit `{}` ({}) does not conform to naming requirements!'.format(commit.subject, commit.hash))
            print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
            exit(1)

        if tito_commit:
            tito_index = index

        if commit.subject == git._SPEC_SUBJECT:
            spec_index = index

    if tito_index < 0:
        print('No commit from `tito tag` found!')
        print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
        exit(1)

    if spec_index < 0:
        print('No [CARRY] commit for `origin.spec` file found!')
        print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
        exit(1)

    if tito_index < spec_index:
        print('Found the `tito tag` commit before the `origin.spec` file commit!')
        print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
        exit(1)

    # Validate that CARRIES have a type.
    carry_types = filter_commits_by_prefix(commits, git._CARRY_PREFIX)

    # Validate that CARRY types are unique across all CARRIES.
    if len(carry_types) != len(set(carry_types)):
        print('Found more than one [CARRY] commit with the same type!')
        print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
        exit(1)

    # Validate that SQUASHES have a type.
    squash_types = filter_commits_by_prefix(commits, git._SQUASH_PREFIX)

    # Validate that all SQUASHES have a corresponding CARRY commit.
    if set(squash_types) & set(carry_types) != set(squash_types):
        print('Not all [SQUASH] commits correspond to a [CARRY] commit!')
        print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
        exit(1)


def filter_commits_by_prefix(commits, prefix):
    types = []
    for commit in commits:
        if commit.subject.startswith(prefix):
            subject = commit.subject[len(prefix):]

            match = re.match(r"\[.*\]", subject)
            if match is None:
                print('Found a {} commit without a type: `{}` ({})'.format(prefix, commit.subject, commit.hash))
                print('For more info, read https://github.com/openshift/aos-cd-jobs/blob/master/docs/proposals/ose-rebase.md#naming-requirements')
                exit(1)

            types.append(match.group(0))

    return types

rebase_path = sys.argv[1]
commits = git.load_commits(rebase_path)

validate_commits(commits)
