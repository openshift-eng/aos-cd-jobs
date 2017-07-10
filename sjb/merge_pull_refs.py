#!/usr/bin/env python
from __future__ import print_function

import os
import subprocess
import sys

if len(sys.argv) != 4:
    print("USAGE: {} WORKING_DIR BASE_BRANCH PULL_REFS".format(sys.argv[0]))
    exit(1)

working_dir = sys.argv[1]
base_branch = sys.argv[2]
# PULL_REFS is expected to be in the form of:
#
# base_branch:commit_sha_of_base_branch,pull_request_no:commit_sha_of_pull_request_no,...
#
# For example:
#
# master:97d901d8e77fff6e8e1b6889e743fe66e7fbbc8b,4:bcb00a13b286bc025ab560c3d703fca81d9aa9c8
#
# And for multiple pull requests that have been batched:
#
# master:97d901d8e77fff6e8e1b6889e743fe66e7fbbc8b,4:bcb00a13b286bc025ab560c3d703fca81d9aa9c8,6:4363gsre7568sfsf346fhg3d703f5ab560c3daa8
pull_refs = sys.argv[3]

os.chdir(working_dir)
subprocess.call(["git", "checkout", "-q", base_branch])

for pull_num in [r.split(':')[0] for r in pull_refs.split(',')][1:]:
	branch = 'pull-{}'.format(pull_num)
	pull_ref = 'pull/{}/head:{}'.format(pull_num, branch)
	print("Fetching and merging PR #{} into {} ...".format(pull_num, base_branch))
	print(subprocess.check_output(["git", "fetch", "origin", pull_ref]).strip())
	print(subprocess.check_output(["git", "merge", branch]).strip())
