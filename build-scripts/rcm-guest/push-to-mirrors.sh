#!/bin/bash
#
# Push the latest puddle to the mirrors
#

set -o xtrace

############
# VARIABLES
############
PUDDLE_TYPE="${1}"
MAJOR_MINOR="${2}"
BUILD_MODE="${3}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"

if [ "$BUILD_MODE" == "release" -o "$BUILD_MODE" == "pre-release" -o "$BUILD_MODE" == "" ]; then
    REPO="enterprise-${MAJOR_MINOR}"
elif [ "$BUILD_MODE" == "online:int" -o "$BUILD_MODE" == "online-int" ]; then  # Maintaining hyphen variant for build/ose job
    REPO="online-int"
elif [ "$BUILD_MODE" == "online:stg" -o "$BUILD_MODE" == "online-stg" ]; then
    REPO="online-stg"
elif [ "$BUILD_MODE" == "online:prod" -o "$BUILD_MODE" == "online-prod" ]; then
    REPO="online-prod"
else
    echo "Unknown BUILD_MODE: ${BUILD_MODE}"
    exit 1
fi

if [ "$(whoami)" == "ocp-build" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi

usage() {
  echo >&2
  echo "Usage `basename $0` [type] [version] <build_mode>" >&2
  echo >&2
  echo "type: simple errata" >&2
  echo "  type of puddle we are pushing" >&2
  echo "version: 3.2 3.3 etc.." >&2
  echo "  What version we are pulling from" >&2
  echo "  For enterprise repos, which release we are pushing to" >&2
  echo "build_mode: release|pre-release|online:int|online:stg" >&2
  echo "  Where to push the puddle to" >&2
  echo "  If it is release or pre-release, then it will go to enterprise-<version>" >&2
  echo "  Default: release" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
fi

if [ "${PUDDLE_TYPE}" == "simple" ] ; then
	# PUDDLEDIR is a symlink to the most recently created puddle.
	PUDDLEDIR="${BASEDIR}/AtomicOpenShift/${MAJOR_MINOR}/latest"
else
	# PUDDLEDIR is a symlink to the most recently created puddle.
	PUDDLEDIR="${BASEDIR}/AtomicOpenShift-errata/${MAJOR_MINOR}/latest"
fi

# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink ${PUDDLEDIR})

echo "Pushing puddle: $LASTDIR"

# Copy all files from the last latest into a directory for the new puddle (jmp: in order to prevent as much transfer as possible by rysnc for things which weren't rebuilt?)
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO} ; cp -r --link latest/ $LASTDIR"

# Copy the local puddle to the new, remote location.
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/ use-mirror-upload.ops.rhcloud.com:/srv/enterprise/${REPO}/${LASTDIR}/

# Replace latest link with new puddle content
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO} ; ln -sfn $LASTDIR latest"

if [ "${PUDDLE_TYPE}" == "simple" ] ; then
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s mash/rhaos-${MAJOR_MINOR}-rhel-7-candidate RH7-RHAOS-${MAJOR_MINOR}"
else
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s RH7-RHAOS-${MAJOR_MINOR}/* ."
fi

# Symlink all builds into "all" builds directory
ALL_DIR="/srv/enterprise/all/${MAJOR_MINOR}"
# Make directory if it hasn't been used (e.g. new release)
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "mkdir -p ${ALL_DIR}"
# Symlink new build into all directory. Replace any existing latest directory to point to the last build.
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd ${ALL_DIR} ; ln -s /srv/enterprise/${REPO}/$LASTDIR ; ln -sfn /srv/enterprise/${REPO}/$LASTDIR latest"

# Synchronize the changes to the mirrors
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh ${REPO} -v
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh all -v
