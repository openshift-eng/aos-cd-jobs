#!/bin/bash

# This approver is to be used during the staging period after
# the staging branch has been cut, where only pull requests
# that fix blocker bugs are allowed to merge.

if [[ $# -ne 1 ]]; then
	echo "[ERROR] Usage: $0 SEVERITY"
	exit 127
else
	severity="$1"
	case "${severity}" in
		"none")
			echo "[ERROR] Only blocker bugs are allowed to merge during stage-cut."
			exit 1
			;;
		"bug")
			echo "[ERROR] Only blocker bugs are allowed to merge during stage-cut."
			exit 1
			;;
		"blocker")
			exit 0
			;;
		*)
			echo "[ERROR] Unknown severity '${severity}': only one of 'none', 'bug', or 'blocker' allowed."
			exit 127
	esac
fi