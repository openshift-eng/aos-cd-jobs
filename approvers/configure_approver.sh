#!/bin/bash

# This script will ensure the correct approver is
# symbolically linked in the appropriate location
# for the branch of the specified repository.

if [[ $# -ne 3 ]]; then
	echo "[ERROR] Usage: $0 REPOSITORY BRANCH STAGE"
	exit 127
else
	repo="$1"
	branch="$2"
	stage="$3"

	approver_dir="/var/lib/jenkins/approvers/openshift/${repo}/${branch}/"
	approver="${approver_dir}/approver"
	rm -f "${approver}"
	mkdir -p "${approver_dir}"

	ln -s "/usr/bin/${stage}_approver.sh" "${approver}"
fi