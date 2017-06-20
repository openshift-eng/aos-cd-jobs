#!/bin/bash

set -o errexit

# A script that generates SSH keys for opsmedic's ~/.ssh/authorized_keys
# that will be used for cluster log gathering, and rotates them keeping
# the last key there.
#
# The keys managed by this script look like this in authorized_keys:
#
#    command="gather-logs" ssh-rsa AAA...Ob logs_access_key_week_22-YMD-H:M:S
#
# where '22' is the week's number. The keys are expected to be rotated weekly,
# so this is a way to check if there's already a key for this week.
#
# The script does not enforce that though and it just issues a warning
# in case an existing key for this week is present.
#
# The new SSH private key is printed to stdout, meant to be collected by
# a Jenkins pipeline running this script.

# Default values for options
AUTHKEYS_FILE="/home/opsmedic/.ssh/authorized_keys"
KEY_COMMENT_PREFIX="logs_access_key_week"
KEY_COMMAND="/usr/bin/verify-gather-logs-operations.py"

# Prepare the comment part of the ssh key to help us identify the key:
# Keep in separate vars because "prefix_WEEKNUM" is what lets us look for the
# presence of a key for this week
KEY_COMMENT="${KEY_COMMENT_PREFIX}_$(date +%V)"
KEY_TIMESTAMP=$(date +%Y%m%d-%H:%M:%S)

# Warn (via stderr) if a key for this week is already there
if grep -q ${KEY_COMMENT} ${AUTHKEYS_FILE}; then
   >&2 echo "WARNING: a key for this week already existed, this will rotate out older keys"
fi

# Set up temporary working space.
# WORKDIR will be deleted when the script terminates
TMPDIR="$HOME/aos-cd/tmp"
mkdir -p "${TMPDIR}"
WORKDIR=$(mktemp -d -p "${TMPDIR}")
WORKFILE=${WORKDIR}/authorized_keys
NEWKEY_FILE=${WORKDIR}/generated_key

function on_exit() {
    rm -rf "${WORKDIR}"
}
trap on_exit EXIT

# Backup current key file
cp -f ${AUTHKEYS_FILE} ${AUTHKEYS_FILE}.bak
cp    ${AUTHKEYS_FILE} ${WORKFILE}

# Rotate keys: leave only the last of the log-gathering keys in the file.
# If there's only 1 or 0 keys in authorized_keys we don't have to rotate
# so we leave the file as is.
if [ "$(grep ${KEY_COMMENT_PREFIX} ${WORKFILE} | wc -l)" -gt 1 ]; then
    LAST_KEY_ID=$(grep ${KEY_COMMENT_PREFIX} ${WORKFILE} |
		      tail -1 | awk '{print $4}')
    # Remove all log gathering keys...
    grep -v ${KEY_COMMENT_PREFIX} ${WORKFILE} > ${AUTHKEYS_FILE} || true
    # ... and copy just the last one
    grep ${LAST_KEY_ID} ${WORKFILE} >> ${AUTHKEYS_FILE}
fi

# Generate new key and add it to authorized_keys
/usr/bin/ssh-keygen -N '' -q \
		    -C "${KEY_COMMENT}-${KEY_TIMESTAMP}" -f ${NEWKEY_FILE}

echo "command=\"${KEY_COMMAND}\" $(cat ${NEWKEY_FILE}.pub)" >> ${AUTHKEYS_FILE}

# Finish: output the newly generated key
cat ${NEWKEY_FILE}
