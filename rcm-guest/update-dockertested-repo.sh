#!/bin/bash
# VARIABLES
LOCAL_BASE_DIR="/mnt/rcm-guest/puddles/RHAOS/Docker/1.9/tested/"
REMOTE_BASE_DIR="/srv/enterprise/rhel/dockertested/"

usage() {
  echo >&2
  echo "Usage `basename $0` [NVR-1] <NVR-2> ... <NVR-n>" >&2
  echo >&2
  echo "NVR = Name-Version-Release of an rpm" >&2
  echo "  NVR Example: docker-1.12.6-9.el7" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 1 ] ; then
  usage
fi

# Clean out old rpms
cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
rm -f *.rpm

# Go through the arguments one at a time, downloading the packages.
while [[ "$#" -ge 1 ]]
do
  cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
  brew download-build --arch=noarch --arch=x86_64 ${$1}
  if [ "$?" != "0" ]; then exit 1 ; fi
  shift
done

# Create the repo
cd ${LOCAL_BASE_DIR}/x86_64/os
createrepo -d .

# Push everything up to the mirrors
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh -o StrictHostKeyChecking=no" ${LOCAL_BASE_DIR} use-mirror-upload.ops.rhcloud.com:${REMOTE_BASE_DIR}
ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh rhel -v

