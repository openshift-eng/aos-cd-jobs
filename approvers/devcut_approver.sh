#!/bin/bash

# This approver is to be used during the frozen period in the
# second half of every sprint, where only pull requests that
# fix bugs are allowed to merge.

if [[ $# -ne 1 ]]; then
	echo "[ERROR] Usage: $0 SEVERITY"
	exit 127
else
	severity="$1"
	case "${severity}" in
		"none")
			echo "[ERROR] Only bugs and blocker bugs are allowed to merge during dev-cut."
			exit 1
			;;
		"bug")
			exit 0
			;;
		"blocker")
			exit 0
			;;
		*)
			echo "[ERROR] Unknown severity '${severity}': only one of 'none', 'bug', or 'blocker' allowed."
			exit 127
	esac
fi