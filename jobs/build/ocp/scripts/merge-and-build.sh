#!/bin/bash

## This script must run with an ssh key for openshift-bot loaded.
export PS4='${LINENO}: '
set -o xtrace

set -o errexit
set -o nounset
set -o pipefail

# Path for merge-and-build script
MB_PATH=$(readlink -f $0)

echo
echo "=========="
echo "Sync git to dist-git repos"
echo "=========="
ose_images.sh --user ocp-build compare_nodocker --branch rhaos-${OSE_VERSION}-rhel-7 --group base

echo
echo "=========="
echo "Update Dockerfiles to new version"
echo "=========="
ose_images.sh --user ocp-build update_docker --branch rhaos-${OSE_VERSION}-rhel-7 --group base --force --release 1 --version "v${VERSION}"

echo
echo "=========="
echo "Build Images"
echo "=========="
ose_images.sh --user ocp-build build_container --branch rhaos-${OSE_VERSION}-rhel-7 --group base --repo http://download.lab.bos.redhat.com/rcm-guest/puddles/RHAOS/repos/aos-unsigned-building.repo

if [ "$EARLY_LATEST_HACK" == "true" ]; then
    # Hack to keep from breaking openshift-ansible CI during daylight builds. They need the latest puddle to exist
    # before images are pushed to registry-ops in order for their current CI implementation to work.
    ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
        sh -s "${PUDDLE_CONF}" -b -d -n \
        < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"
fi

echo
echo "=========="
echo "Push Images"
echo "=========="
# Pass PATH to ensure that sudo inherits Jenkins setup of PATH environment variable.
sudo env "PATH=$PATH" ose_images.sh --user ocp-build push_images ${PUSH_EXTRA} --branch rhaos-${OSE_VERSION}-rhel-7 --group base

set +e
# Try pushing to new registry, but don't error for now.
sudo env "PATH=$PATH" ose_images.sh --user ocp-build push_images ${PUSH_EXTRA} --branch rhaos-${OSE_VERSION}-rhel-7 --group base --push_reg registry.reg-aws.openshift.com:443/online
set -e

echo
echo "=========="
echo "Create latest puddle"
echo "=========="
if [ "$EARLY_LATEST_HACK" != "true" ]; then
    ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
        sh -s "${PUDDLE_CONF}" -b -d -n \
        < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"
fi

# Record the name of the puddle which was created
PUDDLE_NAME=$(ssh ocp-build@rcm-guest.app.eng.bos.redhat.com readlink "/mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/${OSE_VERSION}/latest")
echo -n "${PUDDLE_NAME}" > "${RESULTS}/ose-puddle.name"
echo "Created puddle on rcm-guest: /mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/${OSE_VERSION}/${PUDDLE_NAME}"

echo
echo "=========="
echo "Sync latest puddle to mirrors"
echo "=========="
PUDDLE_REPO=""
case "${BUILD_MODE}" in
online:int ) PUDDLE_REPO="online-int" ;;
online:stg ) PUDDLE_REPO="online-stg" ;;
enterprise ) PUDDLE_REPO="" ;;
enterprise:pre-release ) PUDDLE_REPO="" ;;
* ) echo "BUILD_MODE:${BUILD_MODE} did not match anything we know about, not pushing"
esac

ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
  sh -s "simple" "${OSE_VERSION}" "${PUDDLE_REPO}" \
  < "${WORKSPACE}/build-scripts/rcm-guest/push-to-mirrors.sh"


echo
echo "=========="
echo "Publish the oc binary"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
    sh -s "$OSE_VERSION" "${VERSION}" \
    < "$WORKSPACE/build-scripts/rcm-guest/publish-oc-binary.sh"

for x in "${VERSION}/"{linux/oc.tar.gz,macosx/oc.tar.gz,windows/oc.zip}; do
    curl --silent --show-error --head \
        "https://mirror.openshift.com/pub/openshift-v3/clients/$x" \
        | awk '$2!="200"{print > "/dev/stderr"; exit 1}{exit}'
done


echo
echo "=========="
echo "Gather changelogs"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
    sh -s "$OSE_VERSION" \
    < "$WORKSPACE/scripts/rcm-guest-print-latest-changelog-report.sh" > "${RESULTS}/changelogs.txt"

echo
echo
echo "=========="
echo "Finished"
echo "OCP ${VERSION}"
echo "=========="
