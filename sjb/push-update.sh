#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

job_configs=()
if [[ $# -gt 0 ]]; then
	job_configs=( "$@" )
else
	echo "USAGE: $0 generated/config1.xml generated/config2.xml..."
	exit 1
fi

function retry_post() {
	local job_config="$1"
	local url="$2"

	for (( i = 0; i < 10; i++ )); do
		response="$(
			curl --request "POST"                  \
				 --output /dev/null --silent       \
				 --write-out "%{http_code}"        \
				 --header "Content-Type: text/xml" \
				 --data-binary "@${job_config}"    \
				 --user "${USERNAME}:${PASSWORD}"  \
				 "https://ci.openshift.redhat.com/jenkins/${url}"
		)"

		if [[ "${response}" == "200" ]]; then
			break
		elif [[ "$i" == 9 ]]; then
			tput setaf 1
			tput bold
			echo "[ERROR] Failed to POST ${url}: ${response}"
			tput sgr0
			break
		else
			sleep 0.5 # we're probably failing due to 502 from load anyway...
		fi
	done
}

function update_config() {
	job_config=$1

	job="$( basename "${job_config}" ".xml" )"
	echo "[INFO] Checking for existence of ${job}..."
	if ! curl --request "GET" --fail --silent   \
			  --user "${USERNAME}:${PASSWORD}"  \
			  "https://ci.openshift.redhat.com/jenkins/job/${job}/config.xml" >/dev/null 2>&1; then
		echo "[INFO] Creating ${job}..."
		retry_post "${job_config}" "createItem?name=${job}"
	else
		echo "[INFO] Updating ${job}..."
		retry_post "${job_config}" "job/${job}/config.xml"
	fi
}

for job_config in "${job_configs[@]}"; do
	update_config "${job_config}" &
done

for job in $( jobs -p ); do
	wait "${job}"
done