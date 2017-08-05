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
echo "Tito Building: ose"
echo "=========="
TASK_NUMBER=`tito release --yes --test aos-${OSE_VERSION} | grep 'Created task:' | awk '{print $3}'`
echo "TASK NUMBER: ${TASK_NUMBER}"
echo "TASK URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}"
echo
echo -n "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}" > "${RESULTS}/ose-brew.url"
brew watch-task ${TASK_NUMBER}


echo
echo "=========="
echo "Setup: openshift-ansible"
echo "=========="
rm -rf openshift-ansible
git clone git@github.com:openshift/openshift-ansible.git
cd openshift-ansible/
if [ "${BUILD_MODE}" == "online:stg" ] ; then
    git checkout -q stage
else
  if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
    if [ "${MAJOR}" -eq 3 -a "${MINOR}" -le 5 ] ; then # 3.5 and below maps to "release-1.5"
      git checkout -q release-1.${MINOR}
    else  # Afterwards, version maps directly; 3.5 => "release-3.5"
      git checkout -q release-${OSE_VERSION}
    fi
  fi
fi

echo
echo "=========="
echo "Tito Tagging: openshift-ansible"
echo "=========="
if [ "${MAJOR}" -eq 3 -a "${MINOR}" -le 5 ] ; then # 3.5 and below
    # Use tito's normal progression for older releases
    export TITO_USE_VERSION=""
else
    # For 3.6 onward, match the OCP version
    export TITO_USE_VERSION="--use-version=${VERSION}"
fi

tito tag --accept-auto-changelog ${TITO_USE_VERSION}
git push
git push --tags

echo
echo "=========="
echo "Tito Building: openshift-ansible"
echo "=========="
TASK_NUMBER=`tito release --yes --test aos-${OSE_VERSION} | grep 'Created task:' | awk '{print $3}'`
echo "TASK NUMBER: ${TASK_NUMBER}"
echo "TASK URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}"
echo
echo -n "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}" > "${RESULTS}/openshift-ansible-brew.url"
brew watch-task ${TASK_NUMBER}

pushd "${WORKSPACE}"
COMMIT_SHA="$(git rev-parse HEAD)"
popd
PUDDLE_CONF_BASE="https://raw.githubusercontent.com/openshift/aos-cd-jobs/${COMMIT_SHA}/build-scripts/puddle-conf"
PUDDLE_CONF="${PUDDLE_CONF_BASE}/atomic_openshift-${OSE_VERSION}.conf"

echo
echo "=========="
echo "Building Puddle"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
    sh -s "${PUDDLE_CONF}" -b -d -n -s --label=building \
    < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"


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
