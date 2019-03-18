# usage: ./merge_ocp.sh ./working/ enterprise-3.11 release-3.11 1000
set -e
set -x
WORKING_DIR=$1
OSE_SOURCE_BRANCH=$2
UPSTREAM_SOURCE_BRANCH=$3
DEPTH=$4

pushd ${WORKING_DIR}

# clean up anything left behind in other merges
git reset --hard HEAD
git clean -f

git fetch origin "${OSE_SOURCE_BRANCH}:origin-${OSE_SOURCE_BRANCH}" --depth "${DEPTH}"
git fetch upstream "${UPSTREAM_SOURCE_BRANCH}:upstream-${UPSTREAM_SOURCE_BRANCH}" --depth "${DEPTH}"
git checkout -B "${OSE_SOURCE_BRANCH}" "origin-${OSE_SOURCE_BRANCH}"

# Enable fake merge driver used in our .gitattributes
git config merge.ours.driver true
# Use fake merge driver on specific packages
echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes
echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes
git merge -m "Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}" "upstream-${UPSTREAM_SOURCE_BRANCH}"

git push origin "${OSE_SOURCE_BRANCH}:${OSE_SOURCE_BRANCH}"

popd
