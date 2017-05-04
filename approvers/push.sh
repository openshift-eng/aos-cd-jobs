#!/bin/bash

# This script will deploy the approver scripts to
# the internal and external Jenkins masters. You
# must have your ~/.ssh/config set up to connect
# to them before running this script.

pushd approvers/ >/dev/null

for master in 'ci.openshift' 'ci.dev.openshift'; do
	echo "[INFO] Updating Jenkins master at ${master}..."
	scripts=()
	for stage in 'open' 'devcut' 'stagecut' 'closed'; do
		scripts+=( "${stage}_approver.sh" )
	done

	scripts+=( approve.sh )
	scripts+=( configure_approver.sh )
	scripts+=( list_approvers.sh )
	scp "${scripts[@]}" "${master}:/usr/bin"
done

popd >/dev/null