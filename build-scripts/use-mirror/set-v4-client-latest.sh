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

BASE_DIR="/srv/pub/openshift-v4"

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

# Later, we also need to know what Y stream comes after this one.
MAJOR_NEXT_MINOR=$(echo ${MAJOR_MINOR} |awk -F '[.-]' '{print $1 "." $2+1}')  # e.g. 4.3 -> 4.4

function idempotent_create_link {
    TARGET="$1"
    LINK="$2"
    if [[ ! -e ${LINK} ]]; then
        ln -svfn "${TARGET}" "${LINK}"
        return
    fi
    if [[ "$(readlink -f ${TARGET})" != "$(readlink -f ${LINK})" ]]; then
        ln -svfn "${TARGET}" "${LINK}"
    else
        echo "Link is already up-to-date for ${LINK} -> ${TARGET}"
    fi
}

function create_links {
    local client_base_dir="$1" # e.g. /srv/pub/openshift-v4/s390x/clients/ocp-dev-preview

    # Does this client base directory even exist? (it may not if this arch hasn't built clients yet)
    if [[ ! -d "${client_base_dir}" ]]; then
        echo "Unable to find client base directory: ${client_base_dir} ; will not update ${LINK_NAME}"
        return 1
    fi

    cd "${client_base_dir}"

    # If the release does not exist in the directory
    if [[ ! -d "${RELEASE}" ]]; then
        echo "Unable to find ${RELEASE} directory in ${PWD} ; will not update ${LINK_NAME}"
        return 1
    fi

    MAJOR_MINOR_LINK="${LINK_NAME}-${MAJOR_MINOR}"  # e.g. latest-4.3  or  stable-4.3

    # Here's the easy part. The caller told us what is link is for a given major.minor; set it.
    idempotent_create_link ${RELEASE} ${MAJOR_MINOR_LINK}
    echo "${MAJOR_MINOR_LINK}  now points to ${RELEASE} in ${client_base_dir}"

    # Here's the harder part: we just created something like stable-4.x. If stable-4.x is the highest
    # stable MINOR in a Cincinnati graph, we also want the 'stable' link to point to this release.
    # The way we do this is subtle.. If the existing stable/* directory contains 4.x or anything
    # less than 4.x, we assume we need to update it to point to this new release.
    # Previous versions of this script tried to guess if there was a later minor releases by
    # checking the content of the directory for 4.(x+1), but this is flawed because release
    # candiates are published to these directories before they wind up in Cincinnati graphs.

    if [[ ! -e "${LINK_NAME}" ]]; then
      # If the overall LINK_NAME has never been established, go ahead and create it. Doesn't
      # matter if we are the actual latest for LINK_NAME -- it will be corrected by subsequent runs. This should
      # only happen if we are bootstrapping overall links for the very first time.
      ln -sfn ${RELEASE} ${LINK_NAME}
      echo "Boostrapping ${LINK_NAME} . It now points to ${RELEASE} in ${client_base_dir}"
      return 0
    fi

    # If we reach here, the overall LINK_NAME link exists. We need to check if it points to a
    # release <= the new release minor. CURRENT_OVERALL should evaluate to something like 4.y.z
    CURRENT_OVERALL=$(basename $(readlink -f ${LINK_NAME}))

    # e.g. "echo -e "4.3.5\n4.2.5" | sort -V | tail -n -1"   will print 4.3.5
    HIGHER_RELEASE=$(echo -e "${CURRENT_OVERALL}\n${RELEASE}" | sort -V | tail -n -1)

    if [[ "${HIGHER_RELEASE}" == ${RELEASE} ]]; then
      # This release is ready to be overall
      idempotent_create_link ${RELEASE} ${LINK_NAME}
      echo "Overall ${LINK_NAME} link now points to ${RELEASE} in ${client_base_dir}"
    fi

    return 0
}


# Run the links logic for each architecture passed in.
cd "${BASE_DIR}"
MODE="${ARCHES}"
if [[ "${MODE}" == "all" || "${MODE}" == "any" ]]; then
    # Find any subdirectory with a clients directory; it should be an arch
    ARCHES=$(ls -d */clients/ | awk -F '/' '{print $1}')
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
            echo "No versions current detected in ${USE_CHANNEL} for arch ${qarch} ; No ${LINK_NAME} will be set"
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
    # Check that the clients for this arch exists.
    if [[ ! -d "${target_dir}" ]]; then
        echo "Unable to find clients directory under: ${target_dir}"
        continue
    fi

    if ! create_links "${target_dir}"; then
        echo "Failure creating links in ${target_dir}"
        if [[ "${MODE}" != "any" ]]; then
            echo "This was a required operation; exiting with failure"
            exit 1
        fi
    fi
    timeout 15m /usr/local/bin/push.pub.sh "openshift-v4/$target_path" -v || \
        timeout 5m /usr/local/bin/push.pub.sh "openshift-v4/$target_path" -v
done
