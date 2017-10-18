#!/bin/bash
#
# Push the latest puddle to the mirrors
#

set -o xtrace
set -e

############
# VARIABLES
############
PUDDLE_TYPE="${1}"
FULL_VERSION="${2}"
BUILD_MODE="${3}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
MAJOR_MINOR=$(echo "${FULL_VERSION}" | cut -d . -f 1-2)

if [ "$BUILD_MODE" == "release" ] || [ "$BUILD_MODE" == "pre-release" ] || [ "$BUILD_MODE" == "" ]; then
    REPO="enterprise-${MAJOR_MINOR}"
elif [ "$BUILD_MODE" == "online:int" ] || [ "$BUILD_MODE" == "online-int" ]; then  # Maintaining hyphen variant for build/ose job
    REPO="online-int"
elif [ "$BUILD_MODE" == "online:stg" ] || [ "$BUILD_MODE" == "online-stg" ]; then
    REPO="online-stg"
elif [ "$BUILD_MODE" == "online:prod" ] || [ "$BUILD_MODE" == "online-prod" ]; then
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
  echo "version: e.g. 3.7.0-0.143.7" >&2
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
  PUDDLEDIR=${BASEDIR}/AtomicOpenShift/${MAJOR_MINOR}
else
  PUDDLEDIR=${BASEDIR}/AtomicOpenShift-errata/${MAJOR_MINOR}
fi

# This directory is initially created by puddle as 755.  Setting it to 775
# allows other trusted users to run puddle/write into this directory once the
# directory has been established.
chmod 775 "${PUDDLEDIR}/" || true

# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink --verbose "${PUDDLEDIR}/latest")

# Append version number to facilitate searches on the mirrors.
mv "${PUDDLEDIR}/${LASTDIR}" "${PUDDLEDIR}/${LASTDIR}_v${FULL_VERSION}"
LASTDIR=${LASTDIR}_v${FULL_VERSION}

echo "Pushing puddle: $LASTDIR"

MIRROR_SSH_SERVER="use-mirror-upload.ops.rhcloud.com"
MIRROR_SSH_BASE="ssh ${BOT_USER} -o StrictHostKeychecking=no"
MIRROR_SSH="${MIRROR_SSH_BASE} ${MIRROR_SSH_SERVER}"
MIRROR_PATH="/srv/enterprise/${REPO}"
ALL_DIR="/srv/enterprise/all/${MAJOR_MINOR}"

$MIRROR_SSH sh -s <<-EOF
  set -e
  set -o xtrace

  # In case this repo has never been used before, create it.
  mkdir -p "${MIRROR_PATH}"
  cd "${MIRROR_PATH}"

  # Copy all files from the last latest into a directory for the new puddle
  # (jmp: in order to prevent as much transfer as possible by rysnc for things which weren't rebuilt?)
  cp -r --link latest/ $LASTDIR
EOF

# Copy the local puddle to the new, remote location.
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "${MIRROR_SSH_BASE}" "${PUDDLEDIR}/${LASTDIR}" "${MIRROR_SSH_SERVER}:${MIRROR_PATH}/"

$MIRROR_SSH sh -s <<-EOF
  set -e
  set -o xtrace
  cd "/srv/enterprise/${REPO}"
  # Replace latest link with new puddle content
  ln -sfn $LASTDIR latest

  cd "/srv/enterprise/${REPO}/latest"
  # Some folks use this legacy location for their yum repo configuration
  # e.g. https://euw-mirror1.ops.rhcloud.com/enterprise/enterprise-3.3/latest/RH7-RHAOS-3.3/x86_64/os
  if [ "${PUDDLE_TYPE}" == "simple" ] ; then
  	ln -s mash/rhaos-${MAJOR_MINOR}-rhel-7-candidate RH7-RHAOS-${MAJOR_MINOR}
  else
  	ln -s RH7-RHAOS-${MAJOR_MINOR}/* .
  fi

  # All builds should be tracked in this repository.
  mkdir -p ${ALL_DIR}
  cd "${ALL_DIR}"

  # Symlink new build into all directory.
  ln -s /srv/enterprise/${REPO}/$LASTDIR
  # Replace any existing latest directory to point to the last build.
  ln -sfn /srv/enterprise/${REPO}/$LASTDIR latest

  # Synchronize the changes to the mirrors
  /usr/local/bin/push.enterprise.sh ${REPO} -v
  /usr/local/bin/push.enterprise.sh all -v
EOF
