#!/bin/bash
set -o xtrace
set -o errexit
set -o nounset
set -o pipefail

kinit -k -t $KEYTAB $PRINCIPLE
kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM

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


cd ${WORKPATH}
rm -rf ose origin-web-console
git clone git@github.com:openshift/origin-web-console.git
cd origin-web-console/
git checkout enterprise-3.6

cd ${WORKPATH}
git clone git@github.com:openshift/ose.git
pushd ose
git remote add public git@github.com:openshift/origin
git fetch --all

# Check if there is anything to update.
# Tags are global to the git repo but can only be accessed from the branches they were tagged in
# Switch to the master branch where our latest tags exist for now.
git checkout master
LATEST_TAG=$(git describe --abbrev=0 --tags)
LATEST_TITO_COMMIT_MERGE=$(git log -1 $LATEST_TAG --pretty=%s)
LATEST_TITO_COMMIT_REBASE=$(git log $(git merge-base fake-master public/master)..fake-master --pretty='%h %s' | grep "Automatic commit of package" | awk '{print $1}')
LATEST_TITO_COMMIT_REBASE=$(git log -1 $LATEST_TITO_COMMIT_REBASE --pretty=%s)
if [[ $LATEST_TITO_COMMIT_MERGE == $LATEST_TITO_COMMIT_REBASE ]]; then
	echo "Nothing to update!"
	return 0
fi

# Prepare Origin branch from which we will rebase on top
# Start from the last commit that got pulled in OSE during the previous rebase.
git checkout public/master -b rebase-target
git reset --hard "$(git merge-base master public/master)"
# Remove specfile updates, we will pick them up again from the master branch.
git checkout fake-master
GIT_SEQUENCE_EDITOR=${WORKSPACE}/scripts/rebase_fake.py git rebase -i rebase-target

# Stage the enterprise branch and work from the new branch to update fake-master
git checkout master -b update-fake-master

# Find the latest tito commit
LATEST_TITO_COMMIT=$(git log -1 $LATEST_TAG --pretty=%h)

# Revert changes by the latest tito commit so we can squash everything and then
# cherry-pick the tito commit.
git revert $LATEST_TITO_COMMIT --no-edit

# Reset to Origin master and pick up all the diff produced by tito. Keep track of
# the commit we want to cherry-pick back to fake-master.
git reset rebase-target
git add .tito origin.spec
git commit -m "[CARRY][BUILD_GEN] Specfile updates"
TITO_SQUASH=$(git log -1 --pretty=%h)

# Cleanup in order to switch branches
git stash
git clean -d -fx ""

# Check if there is a commit for the web-console. Hard reset because we already have
# the updated specfile updates commit ready for cherry-picking.
git checkout fake-master

# Reconstruct fake-master carries.
git cherry-pick $TITO_SQUASH
VC_COMMIT="$(GIT_REF=enterprise-3.6 hack/vendor-console.sh 2>/dev/null | grep "Vendoring origin-web-console" | awk '{print $4}')"
git add pkg/assets/bindata.go
git add pkg/assets/java/bindata.go
if [ "$(git status --porcelain)" ]; then
	git commit -m "[DROP] bump origin-web-console ${VC_COMMIT}"
fi
git cherry-pick $LATEST_TITO_COMMIT

# Rebase on top of the last commit that was brought in with the last rebase.
git rebase rebase-target

# Update fake-master finally!
git push origin fake-master -f
