#!/bin/bash
#
# Push the latest puddle to the mirrors
#

set -e
set -o xtrace

############
# VARIABLES
############
TYPE="${1}"
VERSION="${2}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
if [ "$#" -ge 3 ] ; then
  REPO="${3}"
else
  REPO="enterprise-${VERSION}"
fi
MYUID="$(id -u)"
if [ "${MYUID}" == "55003" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi


usage() {
  echo >&2
  echo "Usage `basename $0` [type] [version] <repo>" >&2
  echo >&2
  echo "type: simple errata" >&2
  echo "  type of puddle we are pushing" >&2
  echo "version: 3.2 3.3 etc.." >&2
  echo "  What version we are pulling from" >&2
  echo "  For enterprise repos, which release we are pushing to" >&2
  echo "repo: enterprise online-{int,stg,prod}" >&2
  echo "  Where to push the puddle to" >&2
  echo "  If it is enteprise, then it will go to enterprise-<version>" >&2
  echo "  Default: enterprise" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
fi

if [ "${TYPE}" == "simple" ] ; then
	# PUDDLEDIR is a symlink to the most recently created puddle.
	PUDDLEDIR="${BASEDIR}/AtomicOpenShift/${VERSION}/latest"
else
	# PUDDLEDIR is a symlink to the most recently created puddle.
	PUDDLEDIR="${BASEDIR}/AtomicOpenShift-errata/${VERSION}/latest"
fi

# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink ${PUDDLEDIR})

echo "Pushing puddle: $LASTDIR"

# Copy all files from the last latest into a directory for the new puddle (jmp: in order to prevent as much transfer as possible by rysnc for things which weren't rebuilt?)
set +e
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO} ; cp -r --link latest/ $LASTDIR"
set -e

# Copy the local puddle to the new, remote location.
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/ use-mirror-upload.ops.rhcloud.com:/srv/enterprise/${REPO}/${LASTDIR}/

# Replace latest link with new puddle content
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO} ; ln -sfn $LASTDIR latest"

if [ "${TYPE}" == "simple" ] ; then
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s mash/rhaos-${VERSION}-rhel-7-candidate RH7-RHAOS-${VERSION}"
else
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s RH7-RHAOS-${VERSION}/* ."
fi

# Symlink all builds into "all" builds directory
ALL_DIR="/srv/enterprise/all/${VERSION}"
# Make directory if it hasn't been used (e.g. new release)
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "mkdir -p ${ALL_DIR}"
# Symlink new build into all directory. Replace any existing latest directory to point to the last build.
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd ${ALL_DIR} ; ln -s /srv/enterprise/${REPO}/$LASTDIR ; ln -sfn /srv/enterprise/${REPO}/$LASTDIR latest"

# Synchronize the changes to the mirrors
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh ${REPO} -v
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh all -v
