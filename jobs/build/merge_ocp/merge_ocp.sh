# usage: ./merge_ocp.sh ./working/ enterprise-3.11 release-3.11
set -e
set -x
WORKING_DIR=$1
OSE_SOURCE_BRANCH=$2
UPSTREAM_SOURCE_BRANCH="upstream/$3"

GITHUB_BASE="git@github.com:openshift"

pushd ${WORKING_DIR}

# pull OSE
git clone -b ${OSE_SOURCE_BRANCH} ${GITHUB_BASE}/ose.git --depth 1
cd ose

# Add origin remote so we can merge it in
git remote add upstream ${GITHUB_BASE}/origin.git --no-tags
git fetch --all

# Enable fake merge driver used in our .gitattributes
git config merge.ours.driver true
# Use fake merge driver on specific packages
echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes
echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes
git merge -m 'Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}' ${UPSTREAM_SOURCE_BRANCH}

# git push # probabaly don't run this yet

popd