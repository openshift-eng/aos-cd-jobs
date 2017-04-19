#!/bin/bash
# VARIABLES
LOCAL_BASE_DIR="/mnt/rcm-guest/puddles/RHAOS/Other/kernel-7.4/"
REMOTE_BASE_DIR="/srv/enterprise/rhel/rhel-7.4-kernel-latest/"
# Get latest 7.4 kernel
#KERNEL_NVR="kernel-3.10.0-574.el7"
if [ "${1}" == "" ] ; then
  KERNEL_NVR="$(brew -q latest-build rhel-7.4 kernel | awk '{print $1}')"
else
  KERNEL_NVR="${1}"
fi
## Clean out old rpms
#cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
# rm -f *.rpm
# Pull new rpms into repo
cd ${LOCAL_BASE_DIR}/x86_64/os/Packages/
brew download-build --arch=noarch --arch=x86_64 ${KERNEL_NVR}
if [ "$?" != "0" ]; then exit 1 ; fi
# Create the repo
cd ${LOCAL_BASE_DIR}/x86_64/os
createrepo -d .
# Push everything up to the mirrors
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh -o StrictHostKeyChecking=no" ${LOCAL_BASE_DIR} use-mirror-upload.ops.rhcloud.com:${REMOTE_BASE_DIR}
ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh rhel -v

