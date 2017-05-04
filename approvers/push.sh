#!/bin/bash

# This script will deploy the approver scripts to
# the internal and external Jenkins masters. You
# must have your ~/.ssh/config set up to connect
# to them before running this script.

pushd approvers/ >/dev/null

for master in 'ci.openshift' 'ci.dev.openshift'; do
	echo "[INFO] Updating Jenkins master at ${master}..."
	for stage in 'open' 'devcut' 'stagecut' 'closed'; do
		scp "${stage}_approver.sh" "${master}:/usr/bin"
	done

	scp approve.sh "${master}:/usr/bin"
	scp configure_approver.sh "${master}:/usr/bin"
	scp list_approvers.sh "${master}:/usr/bin"
done

popd >/dev/null