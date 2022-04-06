#!/bin/bash
#
# Push the building atomic-openshift puddle to the mirrors
#

set -o xtrace
set -e

############
# VARIABLES
############
SYMLINK_NAME="${1}"

# There are two VERSION_ARG formats we accept: major.minor.patch-release and major.minor-release.
# If it is the latter, we need to add .0 as the patch for full version.
VERSION_ARG="${2}"
# Split VERSION_ARG between version-release
VERSION=$(echo "${VERSION_ARG}" | cut -d '-' -f 1)
RELEASE=$(echo "${VERSION_ARG}" | cut -d '-' -f 2-)

# If 4.4 is passed in, make it 4.4.0
if [[ "$VERSION" =~ ^[0-9]\.[0-9]$ ]]; then
    VERSION="${VERSION}.0"
fi

FULL_VERSION="${VERSION}-${RELEASE}"

BUILD_MODE="${3}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
MAJOR_MINOR=$(echo "${FULL_VERSION}" | cut -d . -f 1-2)

REPO="enterprise-${MAJOR_MINOR}"

if [ "$BUILD_MODE" == "release" ] || [ "$BUILD_MODE" == "pre-release" ] || [ "$BUILD_MODE" == "" ]; then
    LINK_FROM=""
elif [ "$BUILD_MODE" == "online:int" ] ; then
    LINK_FROM="online-int"
elif [ "$BUILD_MODE" == "online:stg" ] ; then
    LINK_FROM="online-stg"
elif [ "$BUILD_MODE" == "online:prod" ] ; then
    LINK_FROM="online-prod"
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
  echo "Usage `basename $0` [link_name] [version] <build_mode>" >&2
  echo >&2
  echo "link_name: latest" >&2
  echo "  symlink filename to establish to the puddle on rcm-guest/mirror" >&2
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

PUDDLEDIR=${BASEDIR}/plashets/${MAJOR_MINOR}

# This directory is initially created by puddle as 755.  Setting it to 775
# allows other trusted users to run puddle/write into this directory once the
# directory has been established.
chmod 775 "${PUDDLEDIR}/" || true

# dereference the building symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=stream/$(readlink --verbose "${PUDDLEDIR}/stream/building")

# use time of last data modification of building dir as suffix
MODIFIED_TIMESTAMP=$(stat -c %Y "${PUDDLEDIR}/${LASTDIR}")

# Create a symlink on rcm-guest which includes the OCP version. This
# helps find puddles on rcm-guest for particular builds. Note that
# we can't simply rename the directory, because the directory contains
# puddle.repo contains a URL referring to the puddle directory name
# that was created by the puddle command.
VERSIONED_DIR="v${FULL_VERSION}_${MODIFIED_TIMESTAMP}"  # e.g. v3.7.0-0.173.0_2017-06-09.4
ln -sfn "${LASTDIR}" "${PUDDLEDIR}/${VERSIONED_DIR}"

# Create the symlink on rcm-guest. QE appears to use 'latest' here instead of on mirrors.
pushd "$PUDDLEDIR"
ln -sfn "$VERSIONED_DIR"  "$SYMLINK_NAME"
popd
