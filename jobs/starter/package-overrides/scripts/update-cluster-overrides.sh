#!/bin/bash

set -o xtrace
set -e

MYUID="$(id -u)"
if [ "${MYUID}" == "55003" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi

usage() {
  echo >&2
  echo "Usage `basename $0` <online-int|online-stg|online-prod> [NVR-1] [NVR-2] ... [NVR-n]" >&2
  echo >&2
  echo "online-XXXXX indicates the repo that should be populated."
  echo "The NVR information specified will be collected from brew and used to"
  echo "create a repository like https://mirror.openshift.com/enterprise/rhel/aos-cd/overrides-online-XXXXX/x86_64/os/"
  echo "When online-prod is specified, it will simply duplicate the current state of online-stg. No NVR information should be specified in this case."
  echo "NVR = Name-Version-Release of an rpm" >&2
  echo "  NVR Example: docker-1.12.6-9.el7" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

if [ "$#" -lt 1 ] ; then
  usage
fi

if [ "$1" != "online-int" -a "$1" != "online-stg" -a "$1" != "online-prod" ]; then
  echo "Unknown repo: $1"
  usage
fi

if [ "$1" == "online-prod" -a "$#" -gt 1 ]; then
  echo "online-prod can only promote online-stg. Do not specify NVR information"
  usage
fi

REPO_NAME="overrides-${1}"
LOCAL_BASE_DIR="/mnt/rcm-guest/puddles/RHAOS/ContinuousDelivery/${REPO_NAME}/"
REMOTE_BASE_DIR="/srv/enterprise/rhel/aos-cd/${REPO_NAME}"

shift # leave only NVR values

# In case we haven't been run before
mkdir -p ${LOCAL_BASE_DIR}/x86_64/os/Packages/

# Clean out old rpms
cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
rm -f *.rpm

if [ "$REPO_NAME" == "overrides-online-prod" ]; then
	echo "Promoting online-stg to online-prod"
	# If running online-prod, just promote whatever is in stage
	rm -rf "${LOCAL_BASE_DIR}"
	cp -a /mnt/rcm-guest/puddles/RHAOS/ContinuousDelivery/overrides-online-stg ${LOCAL_BASE_DIR}
fi

# Go through the arguments one at a time, downloading the packages.
while [[ "$#" -ge 1 ]]
do
  cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
  brew download-build --arch=noarch --arch=x86_64 ${1}
  if [ "$?" != "0" ]; then echo "Bad NVR: ${1}" ; echo "exiting..." ; exit 5 ; fi
  shift
done

# Create the repo
cd ${LOCAL_BASE_DIR}/x86_64/os
createrepo -d .

# Since this script is piped to ssh, make sure subsequent ssh scripts don't eat up stdin and 
# prematurely eat the rest of the script. Replace stdin with /dev/null
{
	# Push everything up to the mirrors
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com mkdir -p ${REMOTE_BASE_DIR}
	rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${LOCAL_BASE_DIR} use-mirror-upload.ops.rhcloud.com:${REMOTE_BASE_DIR}
	ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh rhel -v
} < /dev/null
