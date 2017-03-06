#!/bin/bash
set -o xtrace

kinit -k -t $KEYTAB $PRINCIPLE

MB_PATH=$(readlink -f $0)
SCRIPTS_DIR=$(dirname $MB_PATH)

set -o errexit
set -o nounset
set -o pipefail

OSE_MASTER="3.5"
if [ "$#" -ne 2 ]; then
  MAJOR="3"
  MINOR="5"  
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

# Ensure ssh-agent is running
eval "$(ssh-agent -s)"

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
  # Load deploy key for cloning/pushing openshift/origin-web-console
  ssh-add -D
  ssh-add ${HOME}/.ssh/origin-web-console/id_rsa
  rm -rf origin-web-console
  git clone git@github.com:openshift/origin-web-console.git
  cd origin-web-console/
  git checkout enterprise-${OSE_VERSION}
## Re-enable once master is 3.6
#  if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
#    git merge master -m "Merge master into enterprise-${OSE_VERSION}"
#    git push
#  fi
  # Add back deploy key for cloning/pushing openshift/ose
  ssh-add -D
  ssh-add ${HOME}/.ssh/id_rsa
fi # End check if we are version 3.2

function sanity_check() {
  echo "Checking if the last commit is the last tito tag commit..."
  last_commit_subject="$( git log HEAD~1..HEAD --pretty=%s )"
  if [[ ! ${last_commit_subject} =~ "Automatic commit of package [atomic-openshift] release"* ]]; then
    set +o xtrace
    echo "[FATAL] The last commit doesn't look like a commit from \`tito\`!"
    echo "[FATAL]   ${last_commit_subject}"
    exit 1
  fi

  echo "Checking if the second to last commit is a webconsole bump commit..."
  webconsole_commit="$( git log HEAD~2..HEAD~1 --pretty=%s )"
  if [[ ! ${webconsole_commit} =~ "[DROP] bump origin-web-console"* ]]; then
    set +o xtrace
    echo "[FATAL] The second to last commit doesn't look like a commit from \`origin-web-console\`!"
    echo "[FATAL]   ${webconsole_commit}"
    exit 1
  fi

  echo "Checking if the third to last commit is the specfile commit..."
  specfile_commit="$( git log HEAD~3..HEAD~2 --pretty=%s )"
  if [[ ${specfile_commit} != "[CARRY][BUILD] Specfile updates" ]]; then
    set +o xtrace
    echo "[FATAL] The third to last commit doesn't look like the specfile commit!"
    echo "[FATAL]   ${specfile_commit}"
    exit 1
  fi
}
readonly -f sanity_check

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
  PREVIOUS_ORIGIN_HEAD=$(git merge-base fake-master upstream/release-1.5)

  # Tags are global to a git repo but accessible only through the branch they were tagged on.
  # This means that a tag created in enterprise-3.5 will not be accessible from master.
  last_tag="$( git describe --abbrev=0 --tags )"

  sanity_check
  # Reset the last three commits and pick up only the tito diff.
  git reset HEAD~3
  git add .tito/ origin.spec
  git commit -m "[CARRY][BUILD] Specfile updates"
  # Drop the previous web console diff - will be regenerated below.
  git checkout -- pkg/assets/bindata.go pkg/assets/java/bindata.go
  set +e
  # Do not error out for now because these tags already exist due to master (we are testing on fake-master)
  git tag "${last_tag}" HEAD
  set -e

  echo
  echo "=========="
  echo "Merge origin into ose stuff"
  echo "=========="
## Switch back once master is 3.6
#  git merge -m "Merge remote-tracking branch upstream/master" upstream/master
  git rebase upstream/release-1.5
  CURRENT_ORIGIN_HEAD=$(git merge-base fake-master upstream/release-1.5)

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
  set +e # Temporarily turn off errexit. THis is failing sometimes. Check with Troy if it is expected.
  # This fails only when there is nothing new to commit, which is normal.
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
