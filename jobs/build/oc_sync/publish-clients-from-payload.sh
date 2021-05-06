#!/bin/bash
set -euo pipefail
export MOBY_DISABLE_PIGZ=true

if [ $# -lt 4 ]; then
    echo "Usage: $0 WORKSPACE VERSION CLIENT_TYPE PULL_SPEC" >&2
    exit 1
fi

WORKSPACE=$1
VERSION=$2
CLIENT_TYPE=$3
PULL_SPEC=$4


MAJOR=$(echo "$VERSION" | cut -d . -f 1)
MINOR=$(echo "$VERSION" | cut -d . -f 2)

GOTRACEBACK=all oc version --client

ARCH=$(skopeo inspect docker://${PULL_SPEC} --config | jq .architecture -r)

if [[ "${ARCH}" == "amd64" ]]; then
    ARCH="x86_64"
elif [[ "${ARCH}" == "arm64" ]]; then
    ARCH="aarch64"
fi

OC_MIRROR_DIR="/srv/pub/openshift-v4/${ARCH}/clients/${CLIENT_TYPE}"

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

#check if already exists
if ssh ${SSH_OPTS} "[ -d ${OC_MIRROR_DIR}/${VERSION} ]";
then
    echo "Already have latest version"
    exit 0
else
    echo "Fetching OCP clients from payload ${VERSION}"
fi

function extract_tools() {
    OUTDIR=$1
    mkdir -p ${OUTDIR}

    #extract all release assests
    GOTRACEBACK=all oc adm release extract --tools --command-os=* ${PULL_SPEC} --to=${OUTDIR}

    pushd ${OUTDIR}
    # External consumers want a link they can rely on.. e.g. .../latest/openshift-client-linux.tgz .
    # So whatever we extract, remove the version specific info and make a symlink with that name.
    for f in *.tar.gz *.bz *.zip *.tgz ; do

        # Is this already a link?
        if [[ -L "$f" ]]; then
            continue
        fi

        # example file names:
        #  - openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
        #  - openshift-client-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
        #  - openshift-install-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
        #  - openshift-client-linux-4.1.9.tar.gz
        #  - openshift-install-mac-4.3.0-0.nightly-s390x-2020-01-06-081137.tar.gz
        #  ...
        # So, match, and store in a group, any non-digit up to the point we find -DIGIT. Ignore everything else
        # until we match (and store in a group) one of the valid file extensions.
        if [[ "$f" =~ ^([^0-9]+)-[0-9].*(tar.gz|tgz|bz|zip)$ ]]; then
            # Create a symlink like openshift-client-linux.tgz => openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
            ln -sfn "$f" "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
        fi
    done
    popd
}

function extract_opm() {
    OUTDIR=$1
    mkdir -p "${OUTDIR}"
    OPERATOR_REGISTRY=$(oc adm release info --image-for operator-registry "$PULL_SPEC")
    # extract opm binaries
    BINARIES=(opm)
    PLATFORMS=(linux)
    if [ "$ARCH" == "x86_64" ]; then  # For x86_64, we have binaries for macOS and Windows
        BINARIES+=(darwin-amd64-opm windows-amd64-opm)
        PLATFORMS+=(mac windows)
    fi

    if [ "$MAJOR" -eq 4 ] && [ "$MINOR" -le 6 ]; then
        PREFIX=/usr/bin
    else  # for 4.7+, opm binaries are at /usr/bin/registry/
        PREFIX=/usr/bin/registry
    fi

    PATH_ARGS=()
    for binary in ${BINARIES[@]}; do
        PATH_ARGS+=(--path "$PREFIX/$binary:$OUTDIR")
    done

    GOTRACEBACK=all oc image extract --confirm --only-files "${PATH_ARGS[@]}" -- "$OPERATOR_REGISTRY"

    # Compress binaries into tar.gz files and calculate sha256 digests
    pushd "$OUTDIR"
    for idx in ${!BINARIES[@]}; do
        binary=${BINARIES[idx]}
        platform=${PLATFORMS[idx]}
        chmod +x "$binary"
        tar -czvf "opm-$platform-$VERSION.tar.gz" "$binary"
        rm "$binary"
        ln -sf "opm-$platform-$VERSION.tar.gz" "opm-$platform.tar.gz"
        sha256sum "opm-$platform-$VERSION.tar.gz" >> sha256sum.txt
    done
    popd
}

case "$CLIENT_TYPE" in
ocp|ocp-dev-preview)
    OUTDIR=${WORKSPACE}/tools/${VERSION}
    >&2 echo "Extracting client tools..."
    extract_tools "$OUTDIR"
    if [ "$MAJOR" -eq 4 ] && [ "$MINOR" -lt 6 ]; then
        >&2 echo "Will not extract opm for releases prior to 4.6."
    else
        >&2 echo "Extracting opm..."
        extract_opm "$OUTDIR"
        tree "$OUTDIR"
        cat "$OUTDIR"/sha256sum.txt
    fi
    ;;
*)
    >&2 echo "Unknown CLIENT_TYPE: $CLIENT_TYPE"
    exit 1
    ;;
esac

if [ "${DRY_RUN:-0}" -ne 0 ]; then
    >&2 echo "[DRY RUN] Don't actually sync things to mirror."
    exit 0
fi

#sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${OUTDIR}" \
    use-mirror-upload.ops.rhcloud.com:${OC_MIRROR_DIR}/

retry() {
  local count exit_code
  count=0
  until "$@"; do
    exit_code="$?"
    count=$((count + 1))
    if [[ $count -lt 4 ]]; then
      sleep 5
    else
      return "$exit_code"
    fi
  done
}

# kick off full mirror push
retry ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh "openshift-v4/${ARCH}/clients/${CLIENT_TYPE}/${VERSION}" -v
