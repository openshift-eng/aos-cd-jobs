#!/usr/bin/env python

import sys
import git

def remove_unnecessary_commits(commits):
    for commit in commits:
        if commit.subject.startswith(git._SPEC_SUBJECT):
            commit.action = git.Action.drop
        if commit.subject.startswith(git._TITO_PREFIX):
        	commit.action = git.Action.drop
        if commit.subject.startswith(git._DROP_PREFIX):
        	commit.action = git.Action.drop

    return commits

rebase_path = sys.argv[1]
commits = git.load_commits(rebase_path)
commits = remove_unnecessary_commits(commits)
git.dump_commits(rebase_path, commits)
