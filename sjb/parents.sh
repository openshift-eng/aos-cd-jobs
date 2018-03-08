#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

function parent() {
	local config=$1
	if ! grep -q 'parent' "${config}"; then
		return
	fi

	local parent_config
	parent_config="sjb/config/$( grep -Po "(?<=parent: ')[^']+(?=')" "${config}" )"
	echo "${parent_config}"
	parent "${parent_config}"
}

parent "$1"