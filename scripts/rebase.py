#!/usr/bin/env python

import sys
import os
import re
import git
import sanity_check

def remove_drop_commits(commits):
    """
    Remove commits labelled for removal with
    the '[DROP]' prefix in their commit subject.

    :param commits: commits to prune
    :return: pruned commits
    """
    for commit in commits:
        if commit.subject.startswith(git._DROP_PREFIX):
            commit.action = git.Action.drop

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
    tito_index = commit_index(commits, lambda c: c.subject.startswith(git._TITO_PREFIX))
    spec_index = commit_index(commits, lambda c: c.subject == git._SPEC_SUBJECT)

    tito_commit = commits.pop(tito_index)
    tito_commit.action = git.Action.fixup
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

    # Consolidate all but SQUASH commits.
    carry_commits = []
    reordered_commits = []
    for commit in commits:
        if commit.subject.startswith(git._CARRY_PREFIX):
            carry_commits.append(commit)
        if not commit.subject.startswith(git._SQUASH_PREFIX):
            reordered_commits.append(commit)

    # Consolidate all SQUASH commits.
    all_squash_commits = []
    for commit in commits:
        if commit.subject.startswith(git._SQUASH_PREFIX):
            all_squash_commits.append(commit)

    # Consolidate SQUASH commits for each CARRY.
    for carry_commit in carry_commits:
        stripped_carry_subject = carry_commit.subject[len(git._CARRY_PREFIX):]

        squash_commits = []
        for commit in all_squash_commits:
            stripped_squash_subject = commit.subject[len(git._SQUASH_PREFIX):]
            if commit_types_match(stripped_carry_subject, stripped_squash_subject):
                squash_commits.append(commit)


        # Walk through all SQUASH commits and add them in the right order in reordered_commits.
        carry_commit_index = reordered_commits.index(carry_commit)
        for index, squash_commit in enumerate(squash_commits):
            squash_commit.action = git.Action.fixup
            reordered_commits.insert(carry_commit_index + index + 1, squash_commit)

    return reordered_commits

def commit_types_match(*commits):
    """
    Compare the prefixes of the two provided commits.
    Return whether they are of the same type thus can
    be squashed together.

    :param commits: commits to check for any match
    :return: whether the commits are of the same type
    """
    prefix = os.path.commonprefix(commits)
    match = re.match(r"\[.*\]", prefix)
    return match is not None



rebase_path = sys.argv[1]
commits = git.load_commits(rebase_path)

sanity_check.validate_commits(commits)
commits = remove_drop_commits(commits)
commits = squash_tito_commits(commits)
commits = squash_named_commits(commits)

git.dump_commits(rebase_path, commits)
