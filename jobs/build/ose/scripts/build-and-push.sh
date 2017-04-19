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
BUILDPATH="${HOME}/go-local"
cd $BUILDPATH
export GOPATH=`pwd`
WORKPATH="${BUILDPATH}/src/github.com/openshift/"
echo "GOPATH: ${GOPATH}"
echo "BUILDPATH: ${BUILDPATH}"
echo "WORKPATH ${WORKPATH}"


echo
echo "=========="
echo "Setup and Check"
echo "=========="
cd ${WORKPATH}
rm -rf ose
git clone git@github.com:openshift/ose.git
cd ose
# Re-enable this once 3.6 is the master
#if [ "${OSE_VERSION}" != "${OSE_MASTER}" ] ; then
  git checkout enterprise-${OSE_VERSION}
#fi
export VERSION_NO_V="$(grep Version: origin.spec | awk '{print $2}')"
export VERSION="v${VERSION_NO_V}"
LATEST_BUILD="$(brew list-tagged --latest --quiet rhaos-${OSE_VERSION}-rhel-7-candidate atomic-openshift | awk '{print $1}' | grep ${VERSION_NO_V})"
if [ "${LATEST_BUILD}" == "" ] ; then
  echo
  echo "There is no build for atomic-openshift-${VERSION_NO_V}"
  echo "Run this script again when there is."
  echo "Exiting"
  exit 1
fi
echo ${LATEST_BUILD}

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
