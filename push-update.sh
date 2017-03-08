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

for job_config in "${job_configs[@]}"; do
	job="$( basename "${job_config}" ".xml" )"
	echo "[INFO] Checking for existence of ${job}..."
	if ! curl --request "GET" --fail --silent   \
	          --user "${USERNAME}:${PASSWORD}"  \
	          "https://ci.openshift.redhat.com/jenkins/job/${job}/config.xml" 2>&1 >/dev/null; then
	    echo "[INFO] Creating ${job}..."
	    curl --request "POST"                  \
             --header "Content-Type: text/xml" \
             --data-binary "@${job_config}"    \
             --user "${USERNAME}:${PASSWORD}"  \
             "https://ci.openshift.redhat.com/jenkins/createItem?name=${job}"
	else
        echo "[INFO] Updating ${job}..."
        curl --request "POST"                  \
             --header "Content-Type: text/xml" \
             --data-binary "@${job_config}"    \
             --user "${USERNAME}:${PASSWORD}"  \
             "https://ci.openshift.redhat.com/jenkins/job/${job}/config.xml"
    fi
done
