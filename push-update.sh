#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

for job_config in generated/*.xml; do
	job="$( basename "${job_config}" ".xml" )"
	echo "[INFO] Updating ${job}..."
	curl --request "POST"                  \
	     --header "Content-Type: text/xml" \
	     --data-binary "@${job_config}"    \
	     --user "${USERNAME}:${PASSWORD}"  \
	     "https://ci.openshift.redhat.com/jenkins/job/${job}/config.xml"
done