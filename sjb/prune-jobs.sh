#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

function retry_get() {
	local url="$1"

	local output; output="$( mktemp )"
	for (( i = 0; i < 10; i++ )); do
		if curl --request "GET"                   \
			    --fail --silent                   \
			    --user "${USERNAME}:${PASSWORD}"  \
			    "${url}/api/json" > "${output}"; then
			cat "${output}"
			break
		elif [[ "$i" == 9 ]]; then
			tput setaf 1
			tput bold
			echo "[ERROR] Failed to GET ${url}: $( cat "${output}" )"
			tput sgr0
			break
		else
			sleep 0.5 # we're probably failing due to 502 from load anyway...
		fi
	done
	rm "${output}"
}

function check() {
	local job=$1
	local name; name="$( basename "${job}" '.xml' )"
	local jobConfigJSON; jobConfigJSON="$( retry_get "https://ci.openshift.redhat.com/jenkins/job/${name}" )"
	if [[ "$( jq --raw-output '.lastBuild' <<<"${jobConfigJSON}" )" == "null" ]]; then
		echo "${name}"
		return
	fi
	local lastBuildURL; lastBuildURL="$( jq --raw-output '.lastBuild.url' <<<"${jobConfigJSON}" )"
	local lastBuildJSON; lastBuildJSON="$( retry_get "${lastBuildURL}" )"
	local buildTime; buildTime="$( jq --raw-output '.timestamp' <<<"${lastBuildJSON}" )"
	local now; now="$( date +%s )"
	local since; since="$(( now - buildTime / 1000  ))"
	local cutoff; cutoff="$(( 1 * 60 * 60 * 24 * 30 ))" # 30 days
	if [[ "${since}" -gt "${cutoff}" ]]; then
		echo "${name}"
	fi
}

for job in sjb/generated/*.xml; do
	check ${job} 2>&1 | tee -a /tmp/$( basename "${job}" '.xml' ).log &
done

for job in $( jobs -p ); do
	wait "${job}"
done