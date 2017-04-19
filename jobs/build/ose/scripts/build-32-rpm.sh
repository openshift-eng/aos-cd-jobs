#!/bin/bash
# Build OCP 3.2 rpm
#set -o xtrace
# This has to be run on a machine with golang 1.4
# Exit out if we aren't
GO_VERSION="$(go version | awk '{print $3}')"
if [ "${GO_VERSION}" != "go1.4.2" ] ; then
  echo
  echo "You need to have go1.4.2"
  echo "  No More, No Less"
  echo "Exiting"
  exit 1
fi
OSE_MASTER="3.5"
if [ "$#" -ne 2 ]; then
  MAJOR="3"
  MINOR="2"  
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
mkdir -p ${BUILDPATH}
cd ${BUILDPATH}
export GOPATH=`pwd`
WORKPATH="${BUILDPATH}"
echo "GOPATH: ${GOPATH}"
echo "BUILDPATH: ${BUILDPATH}"
echo "WORKPATH ${WORKPATH}"

echo
echo "=========="
echo "Setup ose stuff"
echo "=========="
cd ${WORKPATH}
rm -rf ose
git clone git@github.com:openshift/ose.git
cd ose
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
echo
echo "=========="
echo "Finished"
echo "OCP ${VERSION}"
echo "=========="
