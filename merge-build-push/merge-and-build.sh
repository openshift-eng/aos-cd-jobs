#!/bin/bash
# Setup
#set -o xtrace
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
if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
  PUSH_EXTRA="--nolatest"
fi
BUILDPATH="${HOME}/go"
cd $BUILDPATH
export GOPATH=`pwd`
WORKPATH="${BUILDPATH}/src/github.com/openshift/"
echo "GOPATH: ${GOPATH}"
echo "BUILDPATH: ${BUILDPATH}"
echo "WORKPATH ${WORKPATH}"

if [ "${OSE_VERSION}" == "3.2" ] ; then
  echo
  echo "=========="
  echo "OCP 3.2 builds will not work in this build enviroment."
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
   if [ "$?" != "0" ]; then exit 1 ; fi
  if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
    # Add proper ssh key
    ssh-add ${HOME}/.ssh/origin-web-console/id_rsa
    git merge master -m "Merge master into enterprise-${OSE_VERSION}"
    # git push
    # REMOVE SLEEP - FOR TESTING ONLY
    echo "Check that this worked"
    sleep 30
  fi
fi # End check if we are version 3.2

echo
echo "=========="
echo "Setup ose stuff"
echo "=========="
cd ${WORKPATH}
rm -rf ose
git clone git@github.com:kargakis/ose.git
cd ose
git checkout fake-master
if [ "${OSE_VERSION}" == "${OSE_MASTER}" ] ; then
  git remote add upstream git@github.com:openshift/origin.git --no-tags
  git fetch --all

  echo
  echo "=========="
  echo "Merge origin into ose stuff"
  echo "=========="
  git rebase upstream/master
  if [ "$?" != "0" ]; then exit 1 ; fi
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
  git commit -m "Merge remote-tracking branch enterprise-${OSE_VERSION}, bump origin-web-console ${VC_COMMIT}"
fi # End check if we are version 3.2

exit 0

# Put local rpm testing here
echo
echo "=========="
echo "Sleeping for a Minute so you can take a quick look"
echo "=========="
sleep 60

echo
echo "=========="
echo "Tito Tagging"
echo "=========="
tito tag --accept-auto-changelog
  if [ "$?" != "0" ]; then exit 1 ; fi
export VERSION="v$(grep Version: origin.spec | awk '{print $2}')"
echo ${VERSION}
git push
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
  if [ "$?" != "0" ]; then exit 1 ; fi

echo
echo "=========="
echo "Building Puddle"
echo "=========="
ssh tdawson@rcm-guest.app.eng.bos.redhat.com "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${OSE_VERSION}.conf -n -s --label=building"

echo
echo "=========="
echo "Update Dockerfiles to new version"
echo "=========="
ose_images.sh update_docker --branch rhaos-${OSE_VERSION}-rhel-7 --group base --force --release 1 --version ${VERSION}
   if [ "$?" != "0" ]; then exit 1 ; fi

echo
echo "=========="
echo "Build Images"
echo "=========="
ose_images.sh build_container --branch rhaos-${OSE_VERSION}-rhel-7 --group base --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo
   if [ "$?" != "0" ]; then exit 1 ; fi

echo
echo "=========="
echo "Push Images"
echo "=========="
sudo ose_images.sh push_images ${PUSH_EXTRA} --branch rhaos-${OSE_VERSION}-rhel-7 --group base
   if [ "$?" != "0" ]; then exit 1 ; fi

echo
echo "=========="
echo "Create latest puddle"
echo "=========="
ssh tdawson@rcm-guest.app.eng.bos.redhat.com "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${OSE_VERSION}.conf"

echo
echo "=========="
echo "Sync latest puddle to mirrors"
echo "=========="
echo "Not run due to permission problems"
echo "Log into rcm-guest and run"
echo "/mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors.sh simple ${OSE_VERSION}"
#ssh user@rcm-guest.app.eng.bos.redhat.com " /mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors.sh simple ${OSE_VERSION}"

echo
echo
echo "=========="
echo "Finished"
echo "OCP ${VERSION}"
echo "=========="
