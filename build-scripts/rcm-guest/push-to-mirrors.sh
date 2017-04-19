#!/bin/bash
#
# Push the latest puddle to the mirrors
#
############
# VARIABLES
############
TYPE="${1}"
VERSION="${2}"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
if [ "$#" -ge 3 ] ; then
  REPO="${3}"
else
  REPO="enterprise-${VERSION}"
fi
MYUID="$(id -u)"
if [ "${MYUID}" == "55003" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi


usage() {
  echo >&2
  echo "Usage `basename $0` [type] [version] <repo>" >&2
  echo >&2
  echo "type: simple errata" >&2
  echo "  type of puddle we are pushing" >&2
  echo "version: 3.2 3.3 etc.." >&2
  echo "  What version we are pulling from" >&2
  echo "  For enterprise repos, which release we are pushing to" >&2
  echo "repo: enterprise online-{int,stg,prod}" >&2
  echo "  Where to push the puddle to" >&2
  echo "  If it is enteprise, then it will go to enterprise-<version>" >&2
  echo "  Default: enterprise" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
fi


if [ "${TYPE}" == "simple" ] ; then
PUDDLEDIR="${BASEDIR}/AtomicOpenShift/${VERSION}/latest/"
LASTDIR=$(readlink ${BASEDIR}/AtomicOpenShift/${VERSION}/latest)
else
PUDDLEDIR="${BASEDIR}/AtomicOpenShift-errata/${VERSION}/latest/"
LASTDIR=$(readlink ${BASEDIR}/AtomicOpenShift-errata/${VERSION}/latest)
fi
echo $LASTDIR

ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO} ; cp -r --link latest/ $LASTDIR ; rm -f latest ; ln -s $LASTDIR latest"
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR} use-mirror-upload.ops.rhcloud.com:/srv/enterprise/${REPO}/latest/
if [ "${TYPE}" == "simple" ] ; then
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s mash/rhaos-${VERSION}-rhel-7-candidate RH7-RHAOS-${VERSION}"
else
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "cd /srv/enterprise/${REPO}/latest ; ln -s RH7-RHAOS-${VERSION}/* ."
fi
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh ${REPO} -v
