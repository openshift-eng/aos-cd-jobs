#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail 
set -o xtrace

cd /data/src/github.com/openshift/origin
hack/build-base-images.sh
OS_BUILD_ENV_PRESERVE=_output/local hack/env OS_ONLY_BUILD_PLATFORMS='linux/amd64' hack/build-rpm-release.sh
sudo systemctl restart docker
hack/build-images.sh
sed -i 's|go/src|data/src|' _output/local/releases/rpms/origin-local-release.repo
sudo cp _output/local/releases/rpms/origin-local-release.repo /etc/yum.repos.d/
