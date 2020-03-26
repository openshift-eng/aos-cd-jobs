#!/usr/bin/env bash

# usage: ./merge_ocp.sh ./working/ enterprise-3.11 release-3.11
set -e
set -x
WORKING_DIR=$1
OSE_SOURCE_BRANCH=$2
UPSTREAM_SOURCE_BRANCH=$3

pushd ${WORKING_DIR}

# clean up anything left behind in other merges
git reset --hard HEAD
git clean -f

git fetch origin "${OSE_SOURCE_BRANCH}:origin-${OSE_SOURCE_BRANCH}"
git fetch upstream "${UPSTREAM_SOURCE_BRANCH}:upstream-${UPSTREAM_SOURCE_BRANCH}"
git checkout -B "${OSE_SOURCE_BRANCH}" "origin-${OSE_SOURCE_BRANCH}"

FF_ONLY_ARG=""

if [[ $OSE_SOURCE_BRANCH == enterprise-3.* ]]; then
    # Enable fake merge driver used in our .gitattributes
    git config merge.ours.driver true
    # Use fake merge driver on specific packages
    echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes
    echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes
else
    # At some point in the future, openshift/ose will be a pure fast-forward of openshift/origin for all 4.x branches.
    # When this change over occurs, we want to be absolutely sure we only fast-forward 4.x branches and do not push
    # merge commits. The following logic attempts to enfore that. The theory of operation is as follows:
    # Up to the time of this writing, ose commits are always either embargoed fixes OR more normally, merge commits
    # pulling content from openshift/origin to openshift/ose. Thus, no commit at the HEAD of openshift/ose should
    # ever be found in openshift/origin. However, then the trigger is pulled, and openshift/origin is force pushed
    # to openshift/ose 4.x branches to start fast-forwarding only, this code will detect the HEAD of openshift/ose
    # in openshift/origin for the first time. At that moment, we should only allow fast-forwarding.
    CURRENT_OSE_HEAD=$(git rev-parse HEAD)
    if git branch -r --contains ${CURRENT_OSE_HEAD} | grep "upstream/" ; then
        echo "Found ose commit ${CURRENT_OSE_HEAD} in upstream openshift/origin. Only permitting fast-forwarding!"
        # With this flag, git will fail with an error if it finds a merge commit is required.
        FF_ONLY_ARG="--ff-only"
    fi
fi

git merge ${FF_ONLY_ARG} -m "Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}" "upstream-${UPSTREAM_SOURCE_BRANCH}"

popd
