#!/bin/bash
set -e

# Must be run from rcm-guest host

############
# USAGE
############
usage() {
  echo >&2
  echo "Usage `basename $0` [type]" >&2
  echo >&2
  echo "Build libra yum repos and push them to the mirrors. ">&2
  echo >&2
  echo "type: int | stg | release " >&2
  echo "  type of repo we are pushing" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

############
# VARIABLES
############

# TODO: We need to handle enterprise builds of openshift-scripts

TYPE="${1}"
case "${TYPE}" in
  online:int | candidate )
    SOURCEREPO="Libra-Candidate"
    LEGACY_DESTREPO="rhel-7-libra-candidate"
    DESTREPO="online-openshift-scripts-int"
  ;;
  online:stg | stage )
    SOURCEREPO="Libra-Stage"
    LEGACY_DESTREPO="rhel-7-libra-stage"
    DESTREPO="online-openshift-scripts-stg"
  ;;
  release )
    SOURCEREPO="Libra"
    LEGACY_DESTREPO="rhel-7-libra"
    DESTREPO="online-openshift-scripts"
 echo "Work is required to release runs"
	exit 1
  ;;
  * )
    echo "ERROR - Unknown BUILD_MODE: ${TYPE}"
    usage
  ;;
esac

# PUDDLEDIR is a symlink to the most recently created puddle.
PUDDLEDIR="/mnt/rcm-guest/puddles/RHAOS/${SOURCEREPO}/7/latest"
# dereference the symlink to the actual directory basename: e.g. "2017-06-09.4"
LASTDIR=$(readlink ${PUDDLEDIR})


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
puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/${LEGACY_DESTREPO}.conf -n

REPO_ROOT="/srv/enterprise/${DESTREPO}"
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "mkdir -p ${REPO_ROOT}/${LASTDIR}"

# Copy the local puddle to the new, remote location. The trailing slashes indicate that directory content and not the directory itself should be transferred.
rsync -aHv --delete-after --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" "${PUDDLEDIR}/" use-mirror-upload.ops.rhcloud.com:${REPO_ROOT}/${LASTDIR}/

# Symlink new build into all directory. Replace any existing latest directory to point to the last build.
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com "ln -sfn ${REPO_ROOT}/${LASTDIR} ${REPO_ROOT}/latest"

# These are legacy locations not used by the Continuous Delivery team any longer.
rsync -aHv --delete-after --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/x86_64/os/ use-mirror-upload.ops.rhcloud.com:/srv/libra/${LEGACY_DESTREPO}/x86_64/
rsync -aHv --delete-after --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh ${BOT_USER} -o StrictHostKeyChecking=no" ${PUDDLEDIR}/source/ use-mirror-upload.ops.rhcloud.com:/srv/libra/${LEGACY_DESTREPO}/source/SRPMS/

# Push the yum repo to the mirrors
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.libra.sh ${LEGACY_DESTREPO} -v
ssh ${BOT_USER} -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh ${DESTREPO} -v
