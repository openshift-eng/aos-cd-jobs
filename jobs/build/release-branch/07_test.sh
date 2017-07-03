#!/bin/bash
set -euo pipefail

sudo chmod a+x /etc/ /etc/origin/ /etc/origin/master/
sudo chmod a+rw /etc/origin/master/admin.kubeconfig
cd /data/src/github.com/openshift/origin/
OS_BUILD_ENV_PRESERVE=_output/local/bin/linux/amd64/extended.test \
  hack/env make build-extended-test
OPENSHIFT_SKIP_BUILD='true' KUBECONFIG=/etc/origin/master/admin.kubeconfig \
  TEST_ONLY='true' JUNIT_REPORT='true' \
  make test-extended SUITE=conformance
