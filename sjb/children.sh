#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

function children() {
	local config=$1

	for child_config in sjb/config/test_cases/*.yml sjb/config/common/test_cases/*.yml; do
		if ! grep -q 'parent' "${child_config}"; then
			continue
		fi

		local parent_config
		parent_config="sjb/config/$( grep -Po "(?<=parent: ')[^']+(?=')" "${child_config}" )"
		if [[ "${parent_config}" == "${config}" ]]; then
			echo "${child_config}"
			children "${child_config}"
		fi
	done
}

children "$1"