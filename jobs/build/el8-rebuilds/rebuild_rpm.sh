#!/bin/bash

set -exuo pipefail
package=$1
version=$2

tmpdir=$(mktemp -d XXXXXXXXXX.distgit)
pushd $tmpdir

export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
rhpkg --user ocp-build clone "$package" --branch "rhaos-$version-rhel-8"
cd "$package"
git rm -f * || :
git checkout "origin/rhaos-$version-rhel-7" -- .
rc=0
if git commit -m "Automated copy from RHEL7 branch"; then
    # we have changes to build
    for i in 1 2 3; do
        if rhpkg push && rhpkg build; then
            rc=0
            break
        fi
        rc=1
        sleep 60
    done
fi
popd
rm -rf $tmpdir
exit $rc
