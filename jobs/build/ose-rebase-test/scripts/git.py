#!/usr/bin/env python

_DROP_PREFIX = '[DROP]'
_SQUASH_PREFIX = '[SQUASH]'
_CARRY_PREFIX = '[CARRY]'
_SPEC_SUBJECT = _CARRY_PREFIX + '[BUILD_GEN] Specfile updates'
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
