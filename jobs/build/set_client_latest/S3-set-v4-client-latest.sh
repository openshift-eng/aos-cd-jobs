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
CLIENT_TYPE=$2   # e.g. auto, ocp or ocp-dev-preview
LINK_NAME=$3   # e.g. latest
ARCHES="${4:-x86_64}"  # e.g. "x86_64 ppc64le s390x aarch64"  OR  "all" to detect arches automatically
FORCE_UPDATE=${FORCE_UPDATE:-0}  # Ignore whether differences are detected and copy into place.

BASE_DIR="pub/openshift-v4"

if [[ $RELEASE =~ ^[0-9].* ]]; then
    MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.3
    PREVIOUS_MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." ($2 - 1)}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.2
    USE_CHANNEL=""
    CHANNEL_PREFIX=""
else
    # Otherwise, the RELEASE arg is assumed to be a channel
    MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $2 "." $3}')  # fast-4.3 -> 4.3
    PREVIOUS_MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $2 "." ($3 - 1)}')  # fast-4.3 -> 4.2
    USE_CHANNEL="${RELEASE}"
    CHANNEL_PREFIX=$(echo ${RELEASE} |awk -F '[.-]' '{print $1}')  # fast-4.3 -> fast
fi

# Run the links logic for each architecture passed in.
MODE="${ARCHES}"
if [[ "${MODE}" == "all" || "${MODE}" == "any" ]]; then
    ARCHES="x86_64 s390x ppc64le aarch64 multi"
fi

# Point rclone to the local config file
function rclone() {
    command rclone --config=${WORKSPACE}/rclone.conf "$@"
}

function transferClientIfNeeded() {
    # Generate rclone config file from the template
    echo "Rendering rclone config file at ${WORKSPACE}/rclone.conf"
    cat /home/jenkins/.config/rclone/rclone.conf.template | envsubst > ${WORKSPACE}/rclone.conf

    # Don't use "aws s3 sync" as it only pays attention to filesize. For files like 'sha256sum.txt' which are
    # usually the same size, it will not update them. rclone can use checksums.

    S3_SRC_PATH="$1"  # e.g. pub/...../adir/
    S3_DEST_PATH="$2"  # e.g. pub/....../bdir/
    # The first name is a registered config on buildvm ($ rclone config edit). The second name is the bucket.
    RCLONE_ADDR="osd-art-account:art-srv-enterprise"
    S3_SRC="${RCLONE_ADDR}/${S3_SRC_PATH}"
    S3_DEST="${RCLONE_ADDR}/${S3_DEST_PATH}"

    CHECK_RESULT="$?"
    # If non-multipart files in the directories are out of sync, then check will return an error
    if ! rclone check "${S3_SRC}" "${S3_DEST}" || [[ "${FORCE_UPDATE}" == "1" ]]; then
        # rclone sync will check md5 sums on non-multipart files and file sizes on multi-part files. If 'check'
        # detects either, just copy (don't sync as it will try to be smart and not copy files with the same name & size).
        rclone copy "${S3_SRC}" "${S3_DEST}"  # Copy over all files, regardless of the difference detected
        rclone sync -c "${S3_SRC}" "${S3_DEST}"  # Run sync to delete any files that should no longer be present.
        # CloudFront will cache files of the same name (e.g. sha256sum.txt), so we need to explicitly invalidate
        aws cloudfront create-invalidation --distribution-id E3RAW1IMLSZJW3 --paths "/${S3_DEST_PATH}*"
    fi

    # Remove the rendered rclone config file
    echo "Removing rclone config file ${WORKSPACE}/rclone.conf"
    rm rclone.conf
}

for arch in ${ARCHES}; do
    if [[ ! -z "$USE_CHANNEL" ]]; then
        qarch="${arch}"
        # Graph uses go arch names; translate from brew arch names
        case "${qarch}" in
            x86_64) qarch="amd64" ;;
            aarch64) qarch="arm64" ;;
        esac
        CHANNEL_RELEASES=$(
            curl -sH "Accept:application/json" --fail --retry 3 --retry-all-errors "https://api.openshift.com/api/upgrades_info/v1/graph?channel=${USE_CHANNEL}&arch=${qarch}" |
              jq '.nodes[].version' -r
        )
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


    if [ "$CLIENT_TYPE" == "auto" ]; then
        if [[ "$RELEASE" =~ -[ef]c\.[0-9]+ ]]; then
            CLIENT_TYPE="ocp-dev-preview"
        else
            CLIENT_TYPE="ocp"
        fi
    fi

    target_path="${arch}/clients/${CLIENT_TYPE}"
    target_dir="${BASE_DIR}/${target_path}"

    MAJOR_MINOR_LINK="${LINK_NAME}-${MAJOR_MINOR}"  # e.g. latest-4.3  or  stable-4.3

    transferClientIfNeeded "${target_dir}/${RELEASE}/" "${target_dir}/${MAJOR_MINOR_LINK}/"

    if [[ "$CLIENT_TYPE" == "ocp" && "${MAJOR_MINOR}" == [0-9]* && "${PREVIOUS_MAJOR_MINOR}" == [0-9]* ]]; then
      # Once clients start publishing to ocp, anything in ocp-dev-preview goes stale. Clean these up for cost
      # and readability. The check on MAJOR_MINOR is just a sanity check that it starts with a digit (e.g. "4.16")
      # so we are deleting only expected items.
      echo "Cleaning up old entries in ocp-dev-preview/"
      aws s3 rm "s3://art-srv-enterprise/pub/openshift-v4/${arch}/clients/ocp-dev-preview/" --recursive --exclude "*" --include "${PREVIOUS_MAJOR_MINOR}.*"
      aws s3 rm "s3://art-srv-enterprise/pub/openshift-v4/${arch}/clients/ocp-dev-preview/" --recursive --exclude "*" --include "${PREVIOUS_MAJOR_MINOR}.*" --profile cloudflare --endpoint-url ${CLOUDFLARE_ENDPOINT}
    fi

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
    # Example LATEST_LINK="candidate-4.16" if LINK_NAME="candidate" and 4.16 is the latest release being published to S3.
    LATEST_LINK=$(aws s3 ls "s3://art-srv-enterprise/${target_dir}/${LINK_NAME}-" | grep PRE | awk '{print $2}' | tr -d '/' | sort -V | tac | head -n 1 || true)

    if [[ "${LATEST_LINK}" == "${MAJOR_MINOR_LINK}" ]]; then
      # If the current major.minor is the latest of this type of link, then update the "overall".
      # For example, if we just copied out stable-4.9 and stable-4.10 does not exist yet, then
      # We should have a directory "stable" with the 4.9 content.
      transferClientIfNeeded "${target_dir}/${RELEASE}/" "${target_dir}/${LINK_NAME}/"

      # Service Delivery links "pre-release" downloads to https://console.redhat.com/openshift/install/pre-release .
      # We want these to point to engineering candidates (ECs).
      # If this is the "candidate" link and the latest release, copy content to that location.
      # Also copy to "latest" for historical consistency.
      if [[ "$LINK_NAME" == "candidate" && "$CLIENT_TYPE" == "ocp-dev-preview" ]]; then
        # This is where console.openshift.com points to find dev-preview artifacts
        transferClientIfNeeded "${target_dir}/${RELEASE}/" "pub/openshift-v4/${arch}/clients/ocp-dev-preview/pre-release/"
        transferClientIfNeeded "${target_dir}/${RELEASE}/" "pub/openshift-v4/${arch}/clients/ocp-dev-preview/latest/"
      fi
    fi
done
