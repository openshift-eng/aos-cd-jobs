#!/bin/bash
#
# Copy the latest stage, to latest prod, on the mirrors
#

set -eu
set -o xtrace

# Settings
BASE_PATH="/srv/enterprise"
MIRROR_SSH_SERVER="use-mirror-upload.ops.rhcloud.com"
SSH_OPTIONS="-o StrictHostKeychecking=no"

usage() {
  echo
  echo "Usage $(basename "$0") <repo>"
  echo
  echo "repo: the path component of the content to sync within ${BASE_PATH}"
  echo "  e.g. 'online', 'online-openshift-scripts'"
  echo
  exit 1
}

# Make sure the repo is provided
if [ "$#" -lt 1 ] ; then
  usage
fi
REPO="${1}"

# Path setup for repo
STG_PATH="${BASE_PATH}/${REPO}-stg"
PROD_PATH="${BASE_PATH}/${REPO}-prod"

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

# Using quoted 'EOF' prevents ${var} expansion
$MIRROR_SSH sh -s <<'EOF'
  LASTDIR=$(readlink "${STG_PATH}"/latest)
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
