#!/bin/bash

# This script will determine if a pull request of the
# given severity should be merging into a a specific
# target branch of a specific repository at this time.

if [[ $# -ne 3 ]]; then
	echo "[ERROR] Usage: $0 REPO BRANCH SEVERITY"
	exit 127
else
	repo="$1"
	branch="$2"
	severity="$3"
	if [[ ! -f "/var/lib/jenkins/approvers/openshift/${repo}/${branch}/approver" ]]; then
		echo "[ERROR] No approval criteria are configured for '${branch}' branch of '${repo}' repo."
		exit 1
	else
		"/var/lib/jenkins/approvers/openshift/${repo}/${branch}/approver" "${severity}"
	fi
fi
