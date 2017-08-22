#!/bin/bash
#
# set -o xtrace
set -e

usage()
{
cat<<EOF
  usage: ${0} --build <build_type> --version <version> --status <COMPLETE||BUILDING> --link-latest
  Options:
    --build: i.e. AtomicOpenShift, AtomicOpenShiftOnline
    --version: i.e. 3.6, 3.7
    --status COMPLETE or BUILDING
    --link-latest: symlink latest dir to puddle
EOF
}

BUILD=
VERSION=
STATUS=
LINK_LATEST=0
while [[ "$#" -ge 1 ]];
do
    case "${1}" in
      --build)
        BUILD="$2"
        shift 2;;
      --version)
        VERSION="$2"
        shift 2;;
      --status)
        STATUS="$2"
        shift 2;;
      --link-latest)
        LINK_LATEST=1
        shift 1;;
      *)
        break
        echo "OTHER: ${1}";;
   esac
done

if [[ -z ${BUILD} ]]; then
  echo "Must provide build type!"
  usage
  exit 1
fi

if [[ -z ${VERSION} ]]; then
  echo "Must provide version!"
  usage
  exit 1
fi

if [[ -z ${STATUS} ]]; then
  echo "Must provide --status [STATUS_VALUE]"
  usage
  exit 1
fi

PUDDLE_BASE_PATH="/mnt/rcm-guest/puddles/RHAOS/${BUILD}/${VERSION}"

# Find latest puddle dir
FULL_PUDDLE_PATH=$(readlink -f ${PUDDLE_BASE_PATH}/building)
echo "Puddle Dir: ${FULL_PUDDLE_PATH}"

echo "Writing ${STATUS} to ${FULL_PUDDLE_PATH}/status.txt"
echo "${STATUS}" > "${FULL_PUDDLE_PATH}/status.txt"

if [[ ${LINK_LATEST} == 1 ]]; then
  echo "Symlinking ${PUDDLE_BASE_PATH}latest to ${FULL_PUDDLE_PATH}"
  ln -sf "${FULL_PUDDLE_PATH}" "${PUDDLE_BASE_PATH}/latest"
fi
