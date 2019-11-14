#!/bin/bash
set -eo pipefail

if [[ -z "$1" ]]; then
    echo "Syntax: $0 <release> <client_type> [arches]"
    echo "  release examples:  4.2.4   or   4.3.0-0.nightly-2019-11-08-080321"
    echo "  client_type: ocp  or  ocp-dev-preview"
    echo "  arches:  - 'all' (autodetect and require success in all)"
    echo "           - 'any' (autodetect and tolerate missing releases for any given arch"
    echo "           - space delimited list like 'x86_64 s390x'"
    exit 1
fi

set -x

if [[ -z "$3" ]]; then
    ARCHES="x86_64"
else
    ARCHES="$3"  # e.g. "x86_64 ppc64le s390x"  OR  "all" to detect arches automatically
fi

# Start enforcing unbound check
set -u

RELEASE=$1    # e.g. 4.2.0 or 4.3.0-0.nightly-2019-11-08-080321
CLIENT_TYPE=$2   # e.g. ocp or ocp-dev-preview

BASE_DIR="/srv/pub/openshift-v4"
MAJOR_MINOR=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.3
# Later, we also need to know what Y stream comes after this one.
MAJOR_NEXT_MINOR=$(echo ${MAJOR_MINOR} |awk -F '[.-]' '{print $1 "." $2+1}')  # e.g. 4.3 -> 4.4


function create_latest_links {
    local client_base_dir="$1" # e.g. /srv/pub/openshift-v4/s390x/clients/ocp-dev-preview

    # Does this client base directory even exist? (it may not if this arch hasn't built clients yet)
    if [[ ! -d "${client_base_dir}" ]]; then
        echo "Unable to find client base directory: ${client_base_dir} ; will not update latest"
        return 1
    fi

    cd "${client_base_dir}"

    # If the release does not exist in the directory
    if [[ ! -d "${RELEASE}" ]]; then
        echo "Unable to find ${RELEASE} directory in ${PWD} ; will not update latest"
        return 1
    fi

    MAJOR_MINOR_LATEST="latest-${MAJOR_MINOR}"

    # Here's the easy part. The caller told us what is latest for a given major.minor; set it.
    ln -svfn ${RELEASE} ${MAJOR_MINOR_LATEST}
    echo "${MAJOR_MINOR_LATEST}  now points to ${RELEASE} in ${client_base_dir}"

    # Here's the harder part - is this major.minor the latest Y stream? If it is, we need to set
    # the overall 'latest'. We already calculated MAJOR_NEXT_MINOR  (e.g. "4.5") so see if that
    # exists someone on the mirror.
    if ls -d "${MAJOR_NEXT_MINOR}".*/ > /dev/null  2>&1; then
        echo "This is not the highest Y release -- will not set overall latest"
        return 0
    fi

    ln -svfn ${RELEASE} latest
    echo "Overall latest now points to ${RELEASE} in ${client_base_dir}"
    return 0
}


# We are transitioning to multi-arch builds. At the time of this writing, directories like
# ${BASE_DIR}/${arch}/clients don't exist -- only ${BASE_DIR}/clients does. This script attempts to account
# for the present and future. if x86_64 doesn't exist yet, we assume clients/ contains the x864_64 payload.

if [[ ! -d "${BASE_DIR}/x86_64" ]]; then
    echo "Can't find x86_64 arch; assuming single arch mode is still in place"
    create_latest_links ${BASE_DIR}/clients/${CLIENT_TYPE}
else

    # Otherwise, multi-arch is enabled. Run the links logic for each architecture passed in.
    cd "${BASE_DIR}"
    MODE="${ARCHES}"
    if [[ "${MODE}" == "all" || "${MODE}" == "any" ]]; then
        # Find any subdirectory with a clients directory; it should be an arch
        ARCHES=$(dirname $(ls -d */clients/))
    fi

    for arch in ${ARCHES}; do
        target_dir="${BASE_DIR}/${arch}/clients/${CLIENT_TYPE}"
        # Check that the clients for this arch exists.
        if [[ ! -d "${target_dir}" ]]; then
            echo "Unable to find clients directory under: ${target_dir}"
            continue
        fi

        if ! create_latest_links "${target_dir}"; then
            echo "Failure creating links in ${target_dir}"
            if [[ "${MODE}" != "any" ]]; then
                echo "This was a required operation; exiting with failure"
                exit 1
            fi
        fi
    done

fi

timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v
