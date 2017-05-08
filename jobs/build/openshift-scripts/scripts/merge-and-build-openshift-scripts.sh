#!/bin/bash
set -o xtrace

MB_PATH=$(readlink -f $0)
SCRIPTS_DIR=$(dirname $MB_PATH)

set -o errexit
set -o nounset
set -o pipefail

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

# Kerberos credeneitslf of ocp-build
kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM

rm -rf online
git clone git@github.com:openshift/online.git
cd online/

if [ "${BUILD_MODE}" == "online:stg" ] ; then
    git checkout -q stage
fi

# Check to see if there have been any changes since the last tag
if git describe --abbrev=0 --tags --exact-match HEAD >/dev/null 2>&1 && [ "${FORCE_REBUILD}" != "true" ] ; then
    echo ; echo "No changes since last tagged build"
    echo "No need to build anything. Stopping."
else
    #There have been changes, so rebuild
    echo
    echo "=========="
    echo "Tito Tagging"
    echo "=========="
    tito tag --accept-auto-changelog
    export VERSION="v$(grep Version: openshift-scripts.spec | awk '{print $2}')"
    
    echo ${VERSION}
    git push
    git push --tags

    echo
    echo "=========="
    echo "Tito building in brew"
    echo "=========="
    TASK_NUMBER=`tito release --yes --test brew | grep 'Created task:' | awk '{print $3}'`
    echo "TASK NUMBER: ${TASK_NUMBER}"
    echo "TASK URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${TASK_NUMBER}"
    echo
    brew watch-task ${TASK_NUMBER}

    echo
    echo "=========="
    echo "Tagging package in brew"
    echo "=========="
    TAG=`git describe --abbrev=0`
    COMMIT=`git log -n 1 --pretty=%h`
    if [ "${BUILD_MODE}" == "online:stg" ] ; then
      brew tag-pkg libra-rhel-7-stage ${TAG}.git.0.${COMMIT}.el7
    else
      brew tag-pkg libra-rhel-7-candidate ${TAG}.git.0.${COMMIT}.el7
    fi

    echo
    echo "=========="
    echo "Build and Push libra repos"
    echo "=========="
    if [ "${BUILD_MODE}" == "online:stg" ] ; then
      ssh ocp-build@rcm-guest.app.eng.bos.redhat.com "/mnt/rcm-guest/puddles/RHAOS/scripts/libra-repo-to-mirrors.sh stage"
    else
      ssh ocp-build@rcm-guest.app.eng.bos.redhat.com "/mnt/rcm-guest/puddles/RHAOS/scripts/libra-repo-to-mirrors.sh candidate"
    fi

    echo
    echo "=========="
    echo "Update Dockerfiles"
    echo "=========="
    ose_images.sh --user ocp-build update_docker --branch libra-rhel-7 --group oso --force --release 1 --version ${VERSION}

    # If we are at the stage mode, dont be messing with the dist-git checking
    if [ "${BUILD_MODE}" != "online:stg" ] ; then
        echo
        echo "=========="
        echo "Sync distgit"
        echo "=========="
        ose_images.sh --user ocp-build compare_nodocker --branch libra-rhel-7 --group oso --force --message "MaxFileSize: 52428800"
    fi

    echo
    echo "=========="
    echo "Build Images"
    echo "=========="
    if [ "${BUILD_MODE}" == "online:stg" ] ; then
      ose_images.sh --user ocp-build build_container --repo http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/repos/oso-stage.repo --branch libra-rhel-7 --group oso
    else
      ose_images.sh --user ocp-build build_container --repo http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/repos/oso-candidate.repo --branch libra-rhel-7 --group oso
    fi

    echo
    echo "=========="
    echo "Push Images"
    echo "=========="
    sudo ose_images.sh --user ocp-build push_images --branch libra-rhel-7 --group oso --release 1

fi

echo
echo "=========="
echo "Finished OpenShift scripts"
echo "=========="
