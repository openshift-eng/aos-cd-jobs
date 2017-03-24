#!/bin/bash
set -o xtrace

kinit -k -t $KEYTAB $PRINCIPLE
kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM

MB_PATH=$(readlink -f $0)
SCRIPTS_DIR=$(dirname $MB_PATH)

set -o errexit
set -o nounset
set -o pipefail

OSE_MASTER="3.6"
if [ "$#" -ne 2 ]; then
  MAJOR="3"
  MINOR="6"
  echo "Please pass in MAJOR and MINOR version"
  echo "Using default of ${MAJOR} and ${MINOR}"
else
  MAJOR="$1"
  MINOR="$2"
fi
OSE_VERSION="${MAJOR}.${MINOR}"
PUSH_EXTRA=""
if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
  PUSH_EXTRA="--nolatest"
fi

# Use the directory relative to this Jenkins job.
BUILDPATH="${WORKSPACE}/go"
mkdir -p $BUILDPATH
cd $BUILDPATH
export GOPATH="$( pwd )"
WORKPATH="${BUILDPATH}/src/github.com/openshift/"
mkdir -p $WORKPATH
echo "GOPATH: ${GOPATH}"
echo "BUILDPATH: ${BUILDPATH}"
echo "WORKPATH ${WORKPATH}"

go get github.com/jteeuwen/go-bindata

if [ "${OSE_VERSION}" == "3.2" ] ; then
  echo
  echo "=========="
  echo "OCP 3.2 builds will not work in this build environment."
  echo "We are exiting now to save you problems later."
  echo "Exiting ..."
  exit 1
fi # End check if we are version 3.2

if [ "${OSE_VERSION}" != "3.2" ] ; then
  echo
  echo "=========="
  echo "Setup origin-web-console stuff"
  echo "=========="
  cd ${WORKPATH}
  rm -rf origin-web-console
  git clone git@github.com:openshift/origin-web-console.git
  cd origin-web-console/
  git checkout enterprise-${OSE_VERSION}
## Re-enable once master is 3.6
#  if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
#    git merge master -m "Merge master into enterprise-${OSE_VERSION}"
#    git push
#  fi
fi # End check if we are version 3.2


echo
echo "=========="
echo "Setup ose stuff"
echo "=========="
cd ${WORKPATH}
rm -rf ose
git clone git@github.com:openshift/ose.git
cd ose
if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
## Remove git checkout once master is 3.6
  git checkout -q fake-master
  git remote add upstream git@github.com:openshift/origin.git --no-tags
  git fetch --all
  PREVIOUS_ORIGIN_HEAD=$(git merge-base fake-master upstream/master)

  # Tags are global to a git repo but accessible only through the branch they were tagged on.
  # This means that a tag created in enterprise-3.5 will not be accessible from master.
  last_tag="$( git describe --abbrev=0 --tags )"

  echo
  echo "=========="
  echo "Merge origin into ose stuff"
  echo "=========="
## Switch back once master is 3.6
#  git merge -m "Merge remote-tracking branch upstream/master" upstream/master
  GIT_SEQUENCE_EDITOR=${WORKSPACE}/scripts/rebase.py git rebase -i upstream/master
  CURRENT_ORIGIN_HEAD=$(git merge-base fake-master upstream/master)
  set +e
  # Do not error out for now because these tags already exist due to master (we are testing on fake-master)
  git tag "${last_tag}" HEAD
  set -e

else
  git checkout -q enterprise-${OSE_VERSION}
  # Check to see if we need to rebuild or not
  HEAD_COMMIT="$(git log -n1 --oneline | awk '{print $1}')"
  OLD_VERSION="v$(grep Version: origin.spec | awk '{print $2}')"
  git checkout -q ${OLD_VERSION}
  LAST_COMMIT="$(git log -n1 --oneline | awk '{print $1}')"
  if [ "${HEAD_COMMIT}" == "${LAST_COMMIT}" ]; then
    echo ; echo "No changes in enterprise-${OSE_VERSION} since last build"
    echo "This is good, so we are exiting with 0"
    exit 0
  else
   echo ; echo "There were changes in enterprise-${OSE_VERSION} since last build"
   echo "So we are moving on with the build"
   git checkout -q enterprise-${OSE_VERSION}
  fi
fi # End check if we are master

if [ "${OSE_VERSION}" != "3.2" ] ; then
  echo
  echo "=========="
  echo "Merge in origin-web-console stuff"
  echo "=========="
  VC_COMMIT="$(GIT_REF=enterprise-${OSE_VERSION} hack/vendor-console.sh 2>/dev/null | grep "Vendoring origin-web-console" | awk '{print $4}')"
  git add pkg/assets/bindata.go
  git add pkg/assets/java/bindata.go
  set +e
  git commit -m "[DROP] bump origin-web-console ${VC_COMMIT}"
  set -e
fi # End check if we are version 3.2

# Put local rpm testing here
echo
echo "=========="
echo "Making sure we have kerberos"
echo "=========="
kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM

echo
echo "=========="
echo "Tito Tagging"
echo "=========="
declare -a changelog
for commit in $( git log "${PREVIOUS_ORIGIN_HEAD}..${CURRENT_ORIGIN_HEAD}" --pretty=%h --no-merges ); do
  changelog+=( "--changelog='$( git log -1 "${commit}" --pretty='%s (%ae)' )'" )
done
tito tag --accept-auto-changelog "${changelog[@]}"
git diff HEAD~1..HEAD > tito_new_diff
cat tito_new_diff
git log --oneline -10
export VERSION="v$(grep Version: origin.spec | awk '{print $2}')"
echo ${VERSION}
exit 0
git push --tags

echo
echo "=========="
echo "Tito building in brew"
echo "=========="
TASK_NUMBER=`tito release --yes --test aos-${OSE_VERSION} | grep 'Created task:' | awk '{print $3}'`
echo "TASK NUMBER: ${TASK_NUMBER}"
echo "TASK URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}"
echo
brew watch-task ${TASK_NUMBER}

echo
echo "=========="
echo "Building Puddle"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${OSE_VERSION}.conf -n -s --label=building"

echo
echo "=========="
echo "Sync git to dist-git repos"
echo "=========="
$SCRIPTS_DIR/ose_images.sh --user ocp-build compare_nodocker --branch rhaos-${OSE_VERSION}-rhel-7 --group base

echo
echo "=========="
echo "Update Dockerfiles to new version"
echo "=========="
$SCRIPTS_DIR/ose_images.sh --user ocp-build update_docker --branch rhaos-${OSE_VERSION}-rhel-7 --group base --force --release 1 --version ${VERSION}

echo
echo "=========="
echo "Build Images"
echo "=========="
$SCRIPTS_DIR/ose_images.sh --user ocp-build build_container --branch rhaos-${OSE_VERSION}-rhel-7 --group base --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo

echo
echo "=========="
echo "Push Images"
echo "=========="
sudo $SCRIPTS_DIR/ose_images.sh --user ocp-build push_images ${PUSH_EXTRA} --branch rhaos-${OSE_VERSION}-rhel-7 --group base

echo
echo "=========="
echo "Create latest puddle"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${OSE_VERSION}.conf"

echo
echo "=========="
echo "Sync latest puddle to mirrors"
echo "=========="
ssh ocp-build@rcm-guest.app.eng.bos.redhat.com " /mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors-bot.sh simple ${OSE_VERSION}"

echo
echo
echo "=========="
echo "Finished"
echo "OCP ${VERSION}"
echo "=========="
