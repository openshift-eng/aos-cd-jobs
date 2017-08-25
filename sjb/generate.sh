#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

pushd sjb >/dev/null
for spec in config/test_cases/*.yml; do
	python -m generate "${spec}" "test"
done

for spec in config/test_suites/*.yml; do
	python -m generate "${spec}" "suite"
done
popd >/dev/null
