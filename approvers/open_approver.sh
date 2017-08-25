#!/bin/bash

# This approver is to be used during the open period in the
# first half of every sprint, where all pull requests regard-
# less of severity are allowed to merge.

if [[ $# -ne 1 ]]; then
	echo "[ERROR] Usage: $0 SEVERITY"
	exit 127
else
	severity="${1,,}"
	case "${severity}" in
		"none")
			exit 0
			;;
		*"lowrisk"*)
			exit 0
			;;
		*"blocker"*)
			exit 0
			;;
		*"bug"*)
			exit 0
			;;
		*)
			echo "[ERROR] Unknown severity '${severity}': only one of 'none', 'bug', 'blocker', or 'lowrisk' allowed."
			exit 127
	esac
fi
