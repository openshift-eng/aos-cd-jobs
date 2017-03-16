#!/bin/bash
set -o xtrace

kinit -k -t $KEYTAB $PRINCIPLE

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

# Ensure ssh-agent is running
eval "$(ssh-agent -s)"

# Kerberos credeneitslf of ocp-build
kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM

# Load deploy key for cloning/pushing openshift/openshift-online
ssh-add -D
ssh-add ${HOME}/.ssh/openshift-online/id_rsa

rm -rf online
git clone git@github.com:openshift/online.git
cd online/

# Check to see if there have been any changes since the last tag
if git describe --abbrev=0 --tags --exact-match HEAD >/dev/null 2>&1; then
    echo ; echo "No changes since last tagged build"
    echo "This is fine, continuing build"
else
    #There have been changes, so rebuild
    echo
    echo "=========="
    echo "Tito Tagging"
    echo "=========="
    tito tag --accept-auto-changelog
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
    brew tag-pkg libra-rhel-7-candidate ${TAG}.git.0.${COMMIT}.el7
fi

echo
echo "=========="
echo "Update Dockerfiles"
echo "=========="
ose_images.sh --user ocp-build update_docker --branch libra-rhel-7 --group oso --force


echo
echo "=========="
echo "Build Images"
echo "=========="
ose_images.sh --user ocp-build build_container --branch libra-rhel-7 --group oso


echo
echo
echo "=========="
echo "Finished OpenShift scripts"
echo "=========="
