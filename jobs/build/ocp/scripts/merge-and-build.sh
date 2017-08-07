#!/bin/bash

## This script must run with an ssh key for openshift-bot loaded.
export PS4='${LINENO}: '
set -o xtrace

set -o errexit
set -o nounset
set -o pipefail

# Path for merge-and-build script
MB_PATH=$(readlink -f $0)


echo
echo "=========="
echo "Gather changelogs"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
    sh -s "$OSE_VERSION" \
    < "$WORKSPACE/scripts/rcm-guest-print-latest-changelog-report.sh" > "${RESULTS}/changelogs.txt"

echo
echo
echo "=========="
echo "Finished"
echo "OCP ${VERSION}"
echo "=========="
