#!/bin/bash
set -eux
export MOBY_DISABLE_PIGZ=true
WORKSPACE=$1
STREAM=$2
MIRROR=$3
OC_MIRROR_DIR="/srv/pub/openshift-v4/clients/$MIRROR/"

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

# get latest release from release-controller API
wget https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/${STREAM}/latest -O latest

#extract pull_spec
PULL_SPEC=`jq -r '.pullSpec' latest`
if [ "$MIRROR" = "ocp-dev-preview" ]; then
  # point at the published pre-release that will stay around -- registry.svc.ci gets GCed
  PULL_SPEC="${PULL_SPEC/registry.svc.ci.openshift.org\/ocp\/release/quay.io/openshift-release-dev/ocp-release-nightly}"
fi

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
retry ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v
