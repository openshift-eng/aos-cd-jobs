#!/bin/bash
#
# Copy the latest stage, to latest prod, on the mirrors
#

set -eu

# Settings
BASE_PATH="/srv/enterprise"
MIRROR_SSH_SERVER="use-mirror-upload.ops.rhcloud.com"
SSH_OPTIONS="-o StrictHostKeychecking=no"

usage() {
  echo
  echo "Usage `basename $0` <repo>"
  echo
  echo "repo: the path component of the content to sync within ${BASE_PATH}"
  echo "  e.g. 'online', 'online-openshift-scripts'"
  echo
  exit 1
}

# Make sure the repo is provided
if [ "$#" -lt 2 ] ; then
  usage
fi

# Path setup for repo
REPO="${1}"
STG_PATH="${BASE_PATH}/${REPO}-stg"
PROD_PATH="${BASE_PATH}/${REPO}-prod"

# sanity check the repo name: just checking repo-stg, assuming that repo-prod
# would exist if repo-stg does
if [ ! -d ${STG_PATH] ]; then
    echo "ERROR: the provided repo (${REPO}) stage path (${STG_PATH}) does not exist." >&2
    exit 1
fi

# SSH client cmdline setup
if [ "$(whoami)" == "ocp-build" ]; then
  BOT_USER="-l jenkins_aos_cd_bot"
else
  BOT_USER=""
fi
MIRROR_SSH="ssh ${BOT_USER} ${SSH_OPTIONS} ${MIRROR_SSH_SERVER}"

############
# Push
############

$MIRROR_SSH sh -s <<EOF
  LASTDIR=$(readlink ${STG_PATH}/latest)
  echo "latest in stg points to: ${LASTDIR}"
  cd ${PROD_PATH}
  if [ -d ${LASTDIR} ] ; then
     echo "${LASTDIR} already exists in prod, nothing to do"
  else
     cp -r --link ${STG_PATH}/${LASTDIR} ${LASTDIR}
     rm -f latest
     ln -s ${LASTDIR} latest
     /usr/local/bin/push.enterprise.sh -v
  fi
EOF
