#!/bin/bash
#
# Copy the latest stage, to latest prod, on the mirrors
#
############
# VARIABLES
############
MYUID="$(id -u)"
if [ "${MYUID}" == "55003" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi

ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com 'LASTDIR=$(readlink /srv/enterprise/online-stg/latest) ; echo ${LASTDIR} ; cd /srv/enterprise/online-prod/ ;  if [ -d ${LASTDIR} ] ; then echo Already Done; else cp -r --link ../online-stg/${LASTDIR} ${LASTDIR} ; rm -f latest ; ln -s ${LASTDIR} latest ; fi'
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh -v

ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com 'LASTDIR=$(date +%Y-%m-%d) ; echo ${LASTDIR} ; cd /srv/libra/online-prod/ ;  if [ -d ${LASTDIR} ] ; then echo Already Done; else mkdir -p ${LASTDIR}/x86_64/ ; cp -r --link ../rhel-7-libra-stage/x86_64/ ${LASTDIR}/x86_64/os ; rm -f latest ; ln -s ${LASTDIR} latest ; fi'
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.libra.sh online-prod -v
