#!/bin/bash

## This script must run with an ssh key for openshift-bot loaded.
export PS4='${LINENO}: '
set -o xtrace

set -o errexit
set -o nounset
set -o pipefail

function get_version_fields {
    COUNT="$1"

    if [ "$COUNT" == "" ]; then
        echo "Invalid number of Version fields specified: $COUNT"
        return 1
    fi

    V="$(grep Version: origin.spec | awk '{print $2}')"
    # e.g. "3.6.126" => "3 6 126" => wc + awk gives number of independent fields
    export CURRENT_COUNT="$(echo ${V} | tr . ' ' | wc | awk '{print $2}')"

    # If there are more fields than we expect, something has gone wrong and needs human attention.
    if [ "$CURRENT_COUNT" -gt "$COUNT" ]; then
        echo "Unexpected number of fields in current version: $CURRENT_COUNT ; expected less-than-or-equal to $COUNT"
        return 1
    fi

    if [ "$CURRENT_COUNT" -lt "$COUNT" ]; then
        echo -n "${V}"
        while [ "$CURRENT_COUNT" -lt "$COUNT" ]; do
            echo -n ".0"
            CURRENT_COUNT=$(($CURRENT_COUNT + 1))
        done
    else
        # Extract the value of the last field
        MINOREST_FIELD="$(echo -n ${V} | rev | cut -d . -f 1 | rev)"
        NEW_MINOREST_FIELD=$(($MINOREST_FIELD + 1))
        # Cut off the minorest version of the version and append the newly calculated patch version
        echo -n "$(echo ${V} | rev | cut -d . -f 1 --complement | rev).$NEW_MINOREST_FIELD"
    fi
}

echo
echo "=========="
echo "Making sure we have kerberos"
echo "=========="
# Old keytab for original OS1 build machine
# kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM
kinit -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM

# Path for merge-and-build script
MB_PATH=$(readlink -f $0)


if [ "$#" -ne 2 ]; then
  echo "Please pass in MAJOR and MINOR version"
  exit 1
else
  MAJOR="$1"
  MINOR="$2"
fi

OSE_VERSION="${MAJOR}.${MINOR}"
PUSH_EXTRA=""

if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
  PUSH_EXTRA="--nolatest"
fi

if [ -z "$WORKSPACE" ]; then
    echo "WORKSPACE environment variable has not been set. Aborting."
    exit 1
fi

# Use the directory relative to this Jenkins job.
BUILDPATH="${WORKSPACE}"

if [ -d "${BUILDPATH}/src" ]; then
    rm -rf "${BUILDPATH}/src" # Remove any previous clone
fi

RESULTS="${BUILDPATH}/results"
if [ -d "${RESULTS}" ]; then
    rm -rf "${RESULTS}"
fi
mkdir -p "${RESULTS}"

WORKPATH="${BUILDPATH}/src/github.com/openshift/"
mkdir -p ${WORKPATH}
cd ${BUILDPATH}
export GOPATH="$( pwd )"
echo "GOPATH: ${GOPATH}"
echo "BUILDPATH: ${BUILDPATH}"
echo "WORKPATH ${WORKPATH}"
echo "BUILD_MODE ${BUILD_MODE}"

go get github.com/jteeuwen/go-bindata

if [ "${OSE_VERSION}" == "3.2" ] ; then
  echo
  echo "=========="
  echo "OCP 3.2 builds will not work in this build environment."
  echo "We are exiting now to save you problems later."
  echo "Exiting ..."
  exit 1
fi # End check if we are version 3.2

# Do a check to see if OSE_MASTER is incorrect.
if [ ! -z "$(git ls-remote --heads git@github.com:openshift/origin.git release-${OSE_MASTER})" \
    -o \
     ! -z "$(git ls-remote --heads git@github.com:openshift/openshift-ansible.git release-${OSE_MASTER})" \
   ]; then
    echo "A release branch exists for the version claimed in OSE_MASTER=${OSE_MASTER}"
    echo "Something is wrong. A new release branch was probably just cut and you need"
    echo "to update OSE_MASTER in the Jenkinsfile."
    exit 1
fi

echo
echo "=========="
echo "Setup OIT stuff"
echo "=========="


pushd ${BUILDPATH}
OIT_DIR="${BUILDPATH}/enterprise-images/"
rm -rf ${OIT_DIR}
mkdir -p ${OIT_DIR}
OIT_PATH="${OIT_DIR}/oit/oit.py"
git clone git@github.com:openshift/enterprise-images.git ${OIT_DIR}
popd

echo
echo "=========="
echo "Setup origin-web-console stuff"
echo "=========="
cd ${WORKPATH}
rm -rf origin-web-console
git clone git@github.com:openshift/origin-web-console.git
cd origin-web-console/
if [ "${BUILD_MODE}" == "online:stg" ] ; then
  WEB_CONSOLE_BRANCH="stage"
  git checkout "${WEB_CONSOLE_BRANCH}"
else
  WEB_CONSOLE_BRANCH="enterprise-${OSE_VERSION}"
  git checkout "${WEB_CONSOLE_BRANCH}"
  if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
    # We will be re-generating the dist directory, so ignore it for the merge
    echo 'dist/** merge=ours' >> .gitattributes
    # Configure the merge driver for this repo
    git config merge.ours.driver true
    git merge master --no-commit --no-ff

    # Use grunt to rebuild everything in the dist directory
    ./hack/install-deps.sh
    grunt build

    git add dist
    git commit -m "Merge master into enterprise-${OSE_VERSION}" --allow-empty

    git push
    # Clean up any unstaged changes (e.g. .gitattributes)
    git reset --hard HEAD
  fi
fi

echo
echo "=========="
echo "Setup ose stuff"
echo "=========="
cd ${WORKPATH}
rm -rf ose
git clone git@github.com:openshift/ose.git
cd ose

OSE_DIR="${WORKPATH}/ose/"

# Enable fake merge driver used in our .gitattributes
# https://github.com/openshift/ose/commit/02b57ed38d94ba1d28b9bc8bd8abcb6590013b7c
git config merge.ours.driver true

# The number of fields which should be present in the openshift.spec Version field
SPEC_VERSION_COUNT=0

if [ "${BUILD_MODE}" == "enterprise" ]; then

  git checkout -q enterprise-${OSE_VERSION}
  SPEC_VERSION_COUNT=5

else

  # If we are here, we are building master or stage for online

  # Creating a target version allows online:int builds to resume where the last stage build left off in terms
  # of versioning. This should not be necessary when we can safely use a different 'release' in the tito version.
  export TITO_USE_VERSION="--use-version=$(get_post_stage_version origin.spec)"

  if [ "${BUILD_MODE}" == "online:stg" ] ; then
    CURRENT_BRANCH="stage"
    UPSTREAM_BRANCH="upstream/stage"
    SPEC_VERSION_COUNT=4
  elif [ "${BUILD_MODE}" == "enterprise:pre-release" ] ; then
    CURRENT_BRANCH="enterprise-${OSE_VERSION}"
    UPSTREAM_BRANCH="upstream/release-${OSE_VERSION}"
    SPEC_VERSION_COUNT=5
  else # Otherwise, online:int
    # In general, online:int builds should be pulling from upstream/master. However,
    # we may cut an origin release branch and want to use that branch for a time during
    # online:int builds instead of master. We detect this window by checking the
    # version of master versus the version passed in to the online:int build.
    if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
        CURRENT_BRANCH="enterprise-${OSE_VERSION}"
        UPSTREAM_BRANCH="upstream/release-${OSE_VERSION}"
    else
        CURRENT_BRANCH="master"
        UPSTREAM_BRANCH="upstream/master"
    fi
    SPEC_VERSION_COUNT=3 # No need to change
  fi

  echo "Building from branch: ${CURRENT_BRANCH}"
  git checkout -q ${CURRENT_BRANCH}

  git remote add upstream git@github.com:openshift/origin.git --no-tags
  git fetch --all

  echo
  echo "=========="
  echo "Merge origin into ose stuff"
  echo "=========="
  git merge -m "Merge remote-tracking branch ${UPSTREAM_BRANCH}" "${UPSTREAM_BRANCH}"

fi

VOUT="$(get_version_fields $SPEC_VERSION_COUNT)"
if [ "$?" != "0" ]; then
  echo "Error determining version fields: $VOUT"
  exit 1
fi

export TITO_USE_VERSION="--use-version $VOUT"

echo
echo "=========="
echo "Merge in origin-web-console stuff"
echo "=========="
VC_COMMIT="$(GIT_REF=${WEB_CONSOLE_BRANCH} hack/vendor-console.sh 2>/dev/null | grep "Vendoring origin-web-console" | awk '{print $4}')"
git add pkg/assets/bindata.go
git add pkg/assets/java/bindata.go
set +e # Temporarily turn off errexit. THis is failing sometimes. Check with Troy if it is expected.
if [ "${BUILD_MODE}" == "online:stg" ] ; then
  git commit -m "Merge remote-tracking branch stage, bump origin-web-console ${VC_COMMIT}"
else
  git commit -m "Merge remote-tracking branch enterprise-${OSE_VERSION}, bump origin-web-console ${VC_COMMIT}"
fi
set -e

# Put local rpm testing here

echo
echo "=========="
echo "Tito Tagging: ose"
echo "=========="
tito tag --accept-auto-changelog ${TITO_USE_VERSION}
export VERSION="$(grep Version: origin.spec | awk '{print $2}')"  # should match version arrived at by TITO_USE_VERSOIN
git push
git push --tags

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
echo "Setup: openshift-jenkins"
echo "=========="
pushd ${WORKPATH}
rm -rf jenkins
git clone git@github.com:openshift/jenkins.git
OPENSHIFT_JENKINS_DIR="${WORKPATH}/jenkins/"
cd jenkins/
if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
  if [ "${MAJOR}" -eq 3 ] && [ "${MINOR}" -ge 6 ] ; then # 3.5 and below maps to "release-1.5"
    git checkout -q openshift-${MAJOR}.${MINOR}
  fi
fi
popd

echo
echo "=========="
echo "Setup: openshift-ansible"
echo "=========="
pushd ${WORKPATH}
rm -rf openshift-ansible
git clone git@github.com:openshift/openshift-ansible.git
OPENSHIFT_ANSIBLE_DIR="${WORKPATH}/openshift-ansible/"
cd openshift-ansible/
if [ "${BUILD_MODE}" == "online:stg" ] ; then
    git checkout -q stage
else
  if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
    if [ "${MAJOR}" -eq 3 ] && [ "${MINOR}" -le 5 ] ; then # 3.5 and below maps to "release-1.5"
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
popd

echo
echo "=========="
echo "Signing RPMs"
echo "=========="
# "${WORKSPACE}/build-scripts/sign_rpms.sh" "rhaos-${OSE_VERSION}-rhel-7-candidate" "openshifthosted"

pushd "${WORKSPACE}"
COMMIT_SHA="$(git rev-parse HEAD)"
popd
PUDDLE_CONF_BASE="https://raw.githubusercontent.com/openshift/aos-cd-jobs/${COMMIT_SHA}/build-scripts/puddle-conf"
PUDDLE_CONF="${PUDDLE_CONF_BASE}/atomic_openshift-${OSE_VERSION}.conf"
PUDDLE_SIG_KEY="b906ba72"

echo
echo "=========="
echo "Building Puddle"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
    sh -s -- --conf "${PUDDLE_CONF}" -b -d -n -s --label=building \
    < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"


echo
echo "=========="
echo "Sync git to dist-git repos"
echo "=========="
ose_images.sh --user ocp-build compare_nodocker --branch rhaos-${OSE_VERSION}-rhel-7 --group base

echo
echo "=========="
echo "Run OIT rebase"
echo "=========="

cat >"${OIT_WORKING}/sources.yml" <<EOF
ose: ${OSE_DIR}
jenkins: ${OPENSHIFT_JENKINS_DIR}
openshift-ansible: ${OPENSHIFT_ANSIBLE_DIR}
EOF

${OIT_PATH} --user=ocp-build --metadata-dir ${OIT_DIR} --working-dir ${OIT_WORKING} --group openshift-${OSE_VERSION} \
--sources ${OIT_WORKING}/sources.yml \
images:rebase --version v${VERSION} \
--release 1 \
--message "Updating Dockerfile version and release v${VERSION}-1" --push


echo
echo "=========="
echo "Update Dockerfiles to new version"``
echo "=========="
ose_images.sh --user ocp-build update_docker --branch rhaos-${OSE_VERSION}-rhel-7 --group base --force --release 1 --version "v${VERSION}"

echo
echo "=========="
echo "Build Images"
echo "=========="
ose_images.sh --user ocp-build build_container --branch rhaos-${OSE_VERSION}-rhel-7 --group base --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-building.repo

echo
echo "=========="
echo "Build OIT images"
echo "=========="

${OIT_PATH} --user=ocp-build --metadata-dir ${OIT_DIR} --working-dir ${OIT_WORKING} --group openshift-${OSE_VERSION} \
images:build \
--push-to-defaults --repo-type unsigned

if [ "$EARLY_LATEST_HACK" == "true" ]; then
    # Hack to keep from breaking openshift-ansible CI during daylight builds. They need the latest puddle to exist
    # before images are pushed to registry-ops in order for their current CI implementation to work.
    ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
        sh -s -- --conf "${PUDDLE_CONF}" -b -d -n \
        < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"
fi

echo
echo "=========="
echo "Push Images"
echo "=========="
# Pass PATH to ensure that sudo inherits Jenkins setup of PATH environment variable.
sudo env "PATH=$PATH" ose_images.sh --user ocp-build push_images ${PUSH_EXTRA} --branch rhaos-${OSE_VERSION}-rhel-7 --group base

echo
echo "=========="
echo "Create latest puddle"
echo "=========="
if [ "$EARLY_LATEST_HACK" != "true" ]; then
    ssh ocp-build@rcm-guest.app.eng.bos.redhat.com \
        sh -s -- --conf "${PUDDLE_CONF}" -b -d -n \
        < "${WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh"
fi

# Record the name of the puddle which was created
PUDDLE_NAME=$(ssh ocp-build@rcm-guest.app.eng.bos.redhat.com readlink "/mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/${OSE_VERSION}/latest")
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
  sh -s "simple" "${VERSION}" "${PUDDLE_REPO}" \
  < "${WORKSPACE}/build-scripts/rcm-guest/push-to-mirrors.sh"

# push-to-mirrors.sh creates a symlink on rcm-guest with this new name and makes the
# directory on the mirrors match this name.
echo -n "${PUDDLE_NAME}_v${VERSION}" > "${RESULTS}/ose-puddle.name"

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
