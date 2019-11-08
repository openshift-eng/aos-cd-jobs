#!/bin/bash
set -euxo pipefail

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

LESS=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2 "."  $3 "-0"}')
ABOVE=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2+1 "."  $3 "-0"}')
RELEASE_DIR=$(echo ${RELEASE} |awk -F '[.-]' '{print $1 "." $2}')
Z_LATEST=$((curl -X GET --fail -G https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/4-stable/latest --data-urlencode "in=>${LESS} <${ABOVE}" || echo '{ "name": "none" }') | jq -r  '.name')
Y_LATEST=$((curl -X GET --fail -G https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/4-stable/latest || echo '{ "name": "none" }') | jq -r  '.name')

if [[ "${RELEASE}" != "${Z_LATEST}" ]]; then
    echo "Release ${RELEASE} is not the latest z-stream compare to ${Z_LATEST} on payload 4-stable/latest"
    exit 1
fi

# create latest-{4.y} symlink
ln -svf ${RELEASE} latest-${RELEASE_DIR}

# if ${RELEASE} match the latest y stream, then update latest symlink
if [[ "${RELEASE}" == "${Y_LATEST}" ]]; then
    ln -svf latest-${RELEASE_DIR} latest
fi

#sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    latest-${RELEASE_DIR} \
    latest \
    use-mirror-upload.ops.rhcloud.com:${OC_MIRROR_DIR}

# kick off full mirror push
ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v4 -v
