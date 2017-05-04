#!/bin/bash

# This script will list the current state of all
# configured approvers on the system.

if [[ $# -ne 0 ]]; then
	echo "[ERROR] Usage: $0"
	exit 127
else
	echo -e "Current approver state:\n"
	for repo in /var/lib/jenkins/approvers/openshift/*; do
		echo "openshift/$( basename "${repo}" ):"
		for branch in "${repo}"/*; do
			echo -e "\t$( basename "${branch}" ): $( basename "$( readlink "${branch}/approver" )" "_approver.sh" )"
		done
		echo
	done
fi