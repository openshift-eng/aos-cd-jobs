#!/bin/bash
#
# Push the latest puddle to the mirrors
#

set -o xtrace
set -e

if [ "$#" != "2" ]; then
	echo "Invalid arguments"
	echo "Syntax: $0 <major.minor> <build_mode>"
	echo "  Build Modes: online:int, online:stg, pre-release, release"
	exit 1
fi


VERSION="${1}"
BUILD_MODE="${2}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"

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
PUDDLEDIR="${BASEDIR}/AtomicOpenShiftOnline/${VERSION}/latest"

if [ ! -e "${PUDDLEDIR}" ]; then
	echo "Unable to find latest AtomicOpenShiftOnline build: $PUDDLEDIR"
	exit 1
fi

# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink ${PUDDLEDIR})

echo "Pushing puddle: $LASTDIR"

MIRROR_SSH="ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

# Run a bash script on use-mirror
$MIRROR_SSH sh -s <<-EOF
	set -e
	set -o xtrace
	# In case this repo has never been used before, create it.
	mkdir -p "/srv/enterprise/${REPO}"
	pushd "/srv/enterprise/${REPO}"
		mkdir -p "${LASTDIR}"  # Create our destination directory
		if [ -e "latest" ]; then  # If a previous "latest" directory exists
			# Copy in all the old "latest" files in order to speed up rsync. 
			cp -r --link latest/* "${LASTDIR}"
		fi 
	popd
EOF


# Copy the local puddle to the new directory prepped on use-mirror
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/ use-mirror-upload.ops.rhcloud.com:/srv/enterprise/${REPO}/${LASTDIR}/

$MIRROR_SSH sh -s <<-EOF
	set -e
	set -o xtrace
	cd "/srv/enterprise/${REPO}"
	ln -sfn "${LASTDIR}" "latest"  # replace the old "latest" symlink with one pointing to the newly copied puddle
	/usr/local/bin/push.enterprise.sh "${REPO}" -v
EOF
