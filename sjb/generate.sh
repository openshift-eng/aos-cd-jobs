#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

bin="python"
if which python2 >/dev/null 2>&1; then
    bin="python2"
fi

pushd sjb >/dev/null
for spec in config/test_cases/*.yml; do
	"${bin}" -m generate "${spec}" "test"
done

for spec in config/test_suites/*.yml; do
	"${bin}" -m generate "${spec}" "suite"
done
popd >/dev/null
