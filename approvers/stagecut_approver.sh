#!/bin/bash

# This approver is to be used during the staging period after
# the staging branch has been cut, where only pull requests
# that fix blocker bugs are allowed to merge.

if [[ $# -ne 1 ]]; then
	echo "[ERROR] Usage: $0 SEVERITY"
	exit 127
else
	# make severity lowercase
	severity="${1,,}"
	case "${severity}" in
		"none")
			echo "[ERROR] Only blocker bugs are allowed to merge during stage-cut."
			exit 1
			;;
		*"tooling"*)
			exit 0
			;;
		*"blocker"*)
			exit 0
			;;
		*"bug"*)
			echo "[ERROR] Only blocker bugs are allowed to merge during stage-cut."
			exit 1
			;;
		*)
			echo "[ERROR] Unknown severity '${severity}': only one of 'none', 'bug', 'blocker', or 'tooling' allowed."
			exit 127
	esac
fi
