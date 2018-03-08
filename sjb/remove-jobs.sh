#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

function retry_delete() {
	local job="$1"

	for (( i = 0; i < 10; i++ )); do
		response="$(
			curl --request "POST"                  \
				 --output /dev/null --silent       \
				 --write-out "%{http_code}"        \
				 --header "Content-Type: text/xml" \
				 --data-binary "@${job_config}"    \
				 --user "${USERNAME}:${PASSWORD}"  \
				 "https://ci.openshift.redhat.com/jenkins/job/${job}/doDelete"
		)"

		if [[ "${response}" == "204" ]]; then
			break
		elif [[ "$i" == 9 ]]; then
			tput setaf 1
			tput bold
			echo "[ERROR] Failed to delete ${job}: ${response}"
			tput sgr0
			break
		else
			sleep 0.5 # we're probably failing due to 502 from load anyway...
		fi
	done
}

function prune() {
	job_config=$1

	job="$( basename "${job_config}" ".xml" )"
	echo "[INFO] Checking for existence of ${job}..."
	if curl --request "GET" --fail --silent   \
			--user "${USERNAME}:${PASSWORD}"  \
			"https://ci.openshift.redhat.com/jenkins/job/${job}/config.xml" >/dev/null 2>&1; then
		echo "[INFO] Removing ${job}..."
		retry_delete "${job}"
	fi
}

deleted_configs=( $( git log --all --pretty=format: --name-only --diff-filter=D -- sjb/generated/ | sort | uniq ) )
to_remove=()
for deleted_job_config in "${deleted_configs[@]}"; do
	if [[ ! -s "${deleted_job_config}" ]]; then
		to_remove+=( "${deleted_job_config}" )
	fi
done

for deleted_job_config in "${to_remove[@]}"; do
	prune "${deleted_job_config}" &
done

for job in $( jobs -p ); do
	wait "${job}"
done
