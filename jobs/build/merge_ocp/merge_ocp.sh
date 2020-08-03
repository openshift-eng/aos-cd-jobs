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
    CURRENT_OSE_HEAD=$(git rev-parse HEAD)
    FF_ONLY_ARG="--ff-only"
fi

git merge ${FF_ONLY_ARG} -m "Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}" "upstream-${UPSTREAM_SOURCE_BRANCH}"

popd
