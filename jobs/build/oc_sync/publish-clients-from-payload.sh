#!/bin/bash
set -eux
export MOBY_DISABLE_PIGZ=true
WORKSPACE=$1
VERSION=$2
CLIENT_TYPE=$3
PULL_SPEC=$4

ARCH=$(skopeo inspect docker://${PULL_SPEC} -config | jq .architecture -r)
if [[ "${ARCH}" == "amd64" ]]; then
    ARCH="x86_64"
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

TMPDIR=${WORKSPACE}/tools
mkdir -p "${TMPDIR}"
cd ${TMPDIR}

OUTDIR=${TMPDIR}/${VERSION}
mkdir -p ${OUTDIR}
pushd ${OUTDIR}

#extract all release assests
GOTRACEBACK=all oc version
GOTRACEBACK=all oc adm release extract --tools --command-os=* ${PULL_SPEC} --to=${OUTDIR}


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
