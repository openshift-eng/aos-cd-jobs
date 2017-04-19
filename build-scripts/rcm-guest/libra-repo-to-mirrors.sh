#!/bin/bash
#
# Push the latest puddle to the mirrors
#
############
# USAGE
############
usage() {
  echo >&2
  echo "Usage `basename $0` [type]" >&2
  echo >&2
  echo "Build libra yum repos and push them to the mirrors. ">&2
  echo >&2
  echo "type: int | candidate or stg | stage " >&2
  echo "  type of repo we are pushing" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

############
# VARIABLES
############
TYPE="${1}"
case "${TYPE}" in
  int | candidate )
    SOURCEREPO="Libra-Candidate"
    DESTREPO="rhel-7-libra-candidate"
  ;;
  stg | stage )
    SOURCEREPO="Libra-Stage"
    DESTREPO="rhel-7-libra-stage"
  ;;
  * )
    echo "ERROR: ${TYPE} is not recognized"
    usage
  ;;
esac
PUDDLEDIR="/mnt/rcm-guest/puddles/RHAOS/${SOURCEREPO}/7/latest"
MYUID="$(id -u)"
if [ "${MYUID}" == "55003" ] ; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi

# Make sure they passed something in for us
if [ "$#" -lt 1 ] ; then
  usage
fi

# Build the puddle / yum repo
puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/${DESTREPO}.conf -n

# Push the yum repo to the mirrors
rsync -aHv --delete-after --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/x86_64/os/ use-mirror-upload.ops.rhcloud.com:/srv/libra/${DESTREPO}/x86_64/
rsync -aHv --delete-after --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/source/ use-mirror-upload.ops.rhcloud.com:/srv/libra/${DESTREPO}/source/SRPMS/
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.libra.sh ${DESTREPO} -v

echo "exiting"