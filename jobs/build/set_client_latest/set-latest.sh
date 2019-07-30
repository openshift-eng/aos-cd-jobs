#!/bin/bash
set -ux

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

WORKSPACE=$1
RELEASE=$2
OC_MIRROR_DIR="/srv/pub/openshift-v4/clients/$3/"

curl -I https://mirror.openshift.com/pub/openshift-v4/clients/${3}/${RELEASE} | grep -q "404 Not Found"

if [[ $? -eq 0 ]]; then
    echo "Release ${RELEASE} not found on mirror.openshift.com!"
    exit 1
fi

TMPDIR=${WORKSPACE}/tools
mkdir -p "${TMPDIR}"
cd ${TMPDIR}

# create latest symlink
ln -svf ${RELEASE} latest

#sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    latest \
    use-mirror-upload.ops.rhcloud.com:${OC_MIRROR_DIR}

# kick off full mirror push
ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v
