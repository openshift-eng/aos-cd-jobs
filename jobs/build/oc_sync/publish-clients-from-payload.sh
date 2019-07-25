#!/bin/bash
set -eux

WORKSPACE=$1
STREAM=$2
OC_MIRROR_DIR=$3

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

# get latest release from GitHub API
wget https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/${STREAM}/latest -O latest
#extract pull_spec
PULL_SPEC=`jq -r '.pullSpec' latest`
#extract name
VERSION=`jq -r '.name' latest`

#check if already exists
if ssh ${SSH_OPTS} "[ -d ${OC_MIRROR_DIR}${VERSION} ]";
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
popd

#sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${OUTDIR}" \
    use-mirror-upload.ops.rhcloud.com:${OC_MIRROR_DIR}

# kick off full mirror push
ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v
