#!/bin/bash

# This approver is to be used during the closed period in the
# post-release state, where no pull requests are allowed to
# merge.

if [[ $# -ne 1 ]]; then
	echo "[ERROR] Usage: $0 SEVERITY"
	exit 127
else
	severity="${1,,}"
	case "${severity}" in
		"none")
			echo "[ERROR] This branch is closed for pull requests at this time."
			exit 1
			;;
		*"lowrisk"*)
			echo "[ERROR] This branch is closed for pull requests at this time."
			exit 1
			;;
		*"blocker"*)
			echo "[ERROR] This branch is closed for pull requests at this time."
			exit 1
			;;
		*"bug"*)
			echo "[ERROR] This branch is closed for pull requests at this time."
			exit 1
			;;
		*)
			echo "[ERROR] Unknown severity '${severity}': only one of 'none', 'bug', 'blocker', or 'lowrisk' allowed."
			exit 127
	esac
fi
