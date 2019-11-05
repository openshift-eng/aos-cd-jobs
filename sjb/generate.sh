#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

pushd sjb >/dev/null
for spec in config/test_cases/*.yml; do
	python2 -m generate "${spec}" "test" "xml" &
done

for job in $( jobs -p ); do
	wait "${job}"
done
popd >/dev/null
