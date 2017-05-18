#!/bin/bash

set -o errexit 
set -o nounset 
set -o pipefail 
set -o xtrace

cd /data/src/github.com/openshift/origin
KUBECONFIG=/etc/origin/master/admin.kubeconfig TEST_ONLY='true' JUNIT_REPORT='true' make test-extended SUITE=conformance
