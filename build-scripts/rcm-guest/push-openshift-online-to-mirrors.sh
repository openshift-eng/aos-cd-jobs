#!/bin/bash
#
# Push the latest puddle to the mirrors
#

set -o xtrace
set -e

if [ "$#" != "2" ]; then
	echo "Invalid arguments"
	echo "Syntax: $0 <version> <build_mode>"
	echo "  Build Modes: online:int, online:stg, pre-release, release"
	exit 1
fi


FULL_VERSION="${1}"
BUILD_MODE="${2}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
VERSION=$(echo "${FULL_VERSION}" | cut -d . -f 1-2)

if [ "$BUILD_MODE" == "online:int" ]; then
	REPO="online-openshift-scripts-int"
elif [ "$BUILD_MODE" == "online:stg" ]; then
	REPO="online-openshift-scripts-stg"
elif [ "$BUILD_MODE" == "release" ] || [ "$BUILD_MODE" == "pre-release" ]; then
	REPO="online-openshift-scripts-${VERSION}"
else
	echo "Unknown build mode: $BUILD_MODE"
	exit 1
fi

if [ "$(whoami)" == "ocp-build" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi

# This script is called after a successful build. The build should have created
# a puddle and "latest" should be a symlink to that puddle directory. The goal here
# is to copy this puddle out to an appropriate location on the mirrors.
PUDDLEDIR="${BASEDIR}/AtomicOpenShiftOnline/${VERSION}"

if [ ! -e "${PUDDLEDIR}/latest" ]; then
	echo "Unable to find latest AtomicOpenShiftOnline build: ${PUDDLEDIR}/latest"
	exit 1
fi

# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink --verbose "${PUDDLEDIR}/latest")


# Create a symlink on rcm-guest which includes the version. This
# helps find puddles on rcm-guest for particular builds. Note that
# we can't simply rename the directory, because the directory contains
# puddle.repo contains a URL referring to the puddle directory name
# that was created by the puddle command.
VERSIONED_DIR="${LASTDIR}_v${FULL_VERSION}"  # e.g. 2017-06-09.4_v3.7.0-0.173.0
ln -sfn "${LASTDIR}" "${PUDDLEDIR}/${VERSIONED_DIR}"


echo "Pushing puddle: $LASTDIR"

MIRROR_SSH="ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

# Run a bash script on use-mirror
$MIRROR_SSH sh -s <<-EOF
	# In case this REPO dir has never been used before, create it along
	# with the versioned directory we will be populating.
	mkdir -p "/srv/enterprise/${REPO}/${VERSIONED_DIR}"
EOF

# Copy the local puddle to the new directory prepped on use-mirror. This is
# a staging location before we push out the files to the mirrors. Note that the
# directory name changes to one qualified with the build version.
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" "${PUDDLEDIR}/${LASTDIR}/" "use-mirror-upload.ops.rhcloud.com:/srv/enterprise/${REPO}/${VERSIONED_DIR}/"

$MIRROR_SSH sh -s <<-EOF
	set -e
	set -o xtrace
	cd "/srv/enterprise/${REPO}"
	ln -sfn "${VERSIONED_DIR}" "latest"  # replace the old "latest" symlink with one pointing to the newly copied puddle
	/usr/local/bin/push.enterprise.sh "${REPO}" -v
EOF
