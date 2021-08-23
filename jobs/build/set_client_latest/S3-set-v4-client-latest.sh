#!/bin/bash
set -eo pipefail

# jq needs to be available and is installed in user's home
export PATH="$PATH:/home/jenkins_aos_cd_bot/bin"

if [[ "$#" -lt 3 ]]; then
    echo "Syntax: $0 <release_or_channel> <client_type> <link_name> [arches]"
    echo "  release_or_channel examples: stable-4.3  or  4.2.4   or   4.3.0-0.nightly-2019-11-08-080321"
    echo "  client_type: ocp  or  ocp-dev-preview"
    echo "  link_name: e.g. 'latest', 'stable, 'fast', ..."
    echo "  arches:  - 'all' (autodetect and require success in all)"
    echo "           - 'any' (autodetect and tolerate missing releases for any given arch"
    echo "           - space delimited list like 'x86_64 s390x'"
    exit 1
fi

set -x

# Start enforcing unbound check
set -u

RELEASE=$1    # e.g. 4.2.0 or 4.3.0-0.nightly-2019-11-08-080321
CLIENT_TYPE=$2   # e.g. ocp or ocp-dev-preview
LINK_NAME=$3   # e.g. latest
ARCHES="${4:-x86_64}"  # e.g. "x86_64 ppc64le s390x aarch64"  OR  "all" to detect arches automatically

BASE_DIR="pub/openshift-v4"

if [[ $RELEASE =~ ^[0-9].* ]]; then
    MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.3
    USE_CHANNEL=""
    CHANNEL_PREFIX=""
else
    # Otherwise, the RELEASE arg is assumed to be a channel
    MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $2 "." $3}')  # fast-4.3 -> 4.3
    USE_CHANNEL="${RELEASE}"
    CHANNEL_PREFIX=$(echo ${RELEASE} |awk -F '[.-]' '{print $1}')  # fast-4.3 -> fast
fi

# Run the links logic for each architecture passed in.
MODE="${ARCHES}"
if [[ "${MODE}" == "all" || "${MODE}" == "any" ]]; then
    ARCHES="x86_64 s390x ppc64le 	aarch64"
fi

for arch in ${ARCHES}; do

    if [[ ! -z "$USE_CHANNEL" ]]; then
        qarch="${arch}"
        # Graph uses go arch names; translate from brew arch names
        case "${qarch}" in
            x86_64) qarch="amd64" ;;
            aarch64) qarch="arm64" ;;
        esac
        CHANNEL_RELEASES=$(curl -sH 'Accept:application/json' "https://api.openshift.com/api/upgrades_info/v1/graph?channel=${USE_CHANNEL}&arch=${qarch}" | jq '.nodes[].version' -r)
        if [[ -z "$CHANNEL_RELEASES" ]]; then
            echo "No versions currently detected in ${USE_CHANNEL} for arch ${qarch} ; No ${LINK_NAME} will be set"
            if [[ "${MODE}" == "all" ]]; then
                echo "Missing builds - could not satisfy all mode."
                exit 1
            fi
            continue
        fi
        echo "Found releases in channel ${USE_CHANNEL}: ${CHANNEL_RELEASES}"
        RELEASE=$(echo "${CHANNEL_RELEASES}" | sort -V | tail -n 1)

        if [[ ${RELEASE} != ${MAJOR_MINOR}* ]]; then
            echo "${RELEASE} is latest in ${USE_CHANNEL}, but appears to be from previous release; ignoring"
            continue
        fi

    fi

    target_path="${arch}/clients/${CLIENT_TYPE}"
    target_dir="${BASE_DIR}/${target_path}"

    MAJOR_MINOR_LINK="${LINK_NAME}-${MAJOR_MINOR}"  # e.g. latest-4.3  or  stable-4.3

    aws s3 sync --delete "s3://art-srv-enterprise/${target_dir}/${RELEASE}/" "s3://art-srv-enterprise/${target_dir}/${MAJOR_MINOR_LINK}/"

    # List the all the other "latest-4.x" or "stable-4.x" directory names. s3 ls
    # returns lines lke:
    #                           PRE stable-4.1/
    #                           PRE stable-4.2/
    #                           PRE stable-4.3/
    # So we clean up the output to:
    # stable-4.1
    # stable-4.2
    # ...
    # Then we use sort | tac to order the versions and find the greatest '4.x' directory
    LATEST_LINK=$(aws s3 ls "s3://art-srv-enterprise/${target_dir}/${LINK_NAME}-" | grep PRE | awk '{print $2}' | tr -d '/' | sort -V | tac | head -n 1)

    if [[ "${LATEST_LINK}" == "${MAJOR_MINOR_LINK}" ]]; then
      # If the current major.minor is the latest of this type of link, then update the "overall".
      # For example, if we just copied out stable-4.9 and stable-4.10 does not exist yet, then
      # We should have a directory "stable" with the 4.9 content.
      aws s3 sync --delete "s3://art-srv-enterprise/${target_dir}/${RELEASE}/" "s3://art-srv-enterprise/${target_dir}/${LINK_NAME}/"
    fi
done
