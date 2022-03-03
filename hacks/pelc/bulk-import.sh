#!/usr/bin/env bash

# Script to import package NVRs to PELC - "Product Export License Control"
# https://pelc.engineering.redhat.com/
#
# API docs: https://pelc.engineering.redhat.com/rest/v1/

PELC_ENDPOINT='https://pelc.engineering.redhat.com/rest/v1'

pelc::parse_opt() {
	case "${1}" in
		h  )
			pelc::usage
			exit 0
			;;
		\? )
			pelc::echo_error "Invalid option -${OPTARG}"
			pelc::usage
			exit 1
			;;
	esac
}

pelc::usage() {
	cat <<-EOF
	Usage: `basename $0` <product-release> <brew-tag>
	
	<product-release>
	    You can find a list of product-releases here:
	    https://pelc.engineering.redhat.com/products/
	    Search for "Red Hat OpenShift Container Platform [openshift]"
		in "Product List".
	
	<brew-tag>
	    Brew tag that corresponds with given <product-release>
	    and has the NVRs you wish to import.
	
	Example:
	    $ ./`basename $0` openshift-4.9.z rhaos-4.9-rhel-8-candidate
	
	EOF
}

pelc::echo_error() {
	echo -e "\033[31mERROR: ${1}\033[0m"
}

pelc::preflight_check() {
	for tool in awk brew cat curl jq kinit mktemp; do
		which ${tool} &>/dev/null || {
			pelc::echo_error "${tool}: command not found in \$PATH"
			exit 1
		}
	done
}

pelc::obtain_token() {
	{
		curl "${PELC_ENDPOINT}/auth/obtain_token/"    \
			--insecure --silent --negotiate --user :  \
			--header "Content-Type: application/json" \
		| jq --raw-output '.token'
	} || {
		pelc::echo_error 'Failed to obtain authorization token.'
		pelc::echo_error 'Make sure you `kinit` before running this script.'
		exit 1
	}
}

pelc::bulk_import_package_nvrs() {
	product_release="${1}"
	brew_tag="${2}"
	auth_token="${3}"

	data="$(mktemp)"
	pelc::build_import_json "${product_release}" "${brew_tag}" > ${data}

	curl "${PELC_ENDPOINT}/packages/import/" --insecure \
		--header "Authorization: Token $(auth_token)"   \
		--header "Content-Type: application/json"       \
		--request POST --data @${data}
}

pelc::build_import_json() {
	product_release="${1}"
	brew_tag="${2}"

	pelc::get_all_package_nvrs "${brew_tag}" \
	| jq --raw-input . \
	| jq --compact-output --raw-output --monochrome-output --slurp "{
		\"product_release\": \"${product_release}\",
		\"brew_tag\": \"${brew_tag}\",
		\"package_nvrs\": [ (.[] | { \"package_nvr\": . }) ]
	}"
}

pelc::get_all_package_nvrs() {
	brew latest-build ${1} --all --quiet | awk '{ print $1 }'
}

while getopts ":h" opt; do pelc::parse_opt "${opt}"; done
pelc::preflight_check
test $# -eq 2 || {
	pelc::echo_error 'Wrong number of arguments'
	pelc::usage
	exit 1
}

product_release="${1}"
brew_tag="${2}"
auth_token="$(pelc::obtain_token)"
pelc::bulk_import_package_nvrs "${product_release}" "${brew_tag}" "${auth_token}"
