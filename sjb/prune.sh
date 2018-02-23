#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

for job in sjb/generated/*.xml; do
	name="$( basename "${job}" '.xml' )"
	if [[ -z "$( find sjb/config -type f -name "${name}.yml" )" ]]; then
		echo "Pruning ${job}"
		rm "${job}"
	fi
done