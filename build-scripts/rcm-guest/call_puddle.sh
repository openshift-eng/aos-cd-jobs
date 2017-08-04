#!/bin/bash
#
# Download conf file from URL and call puddle
# Allows keeing all conf files in git and calling directly
#

set -e

if [ "$#" -lt 1 ] ; then
  echo "call_puddle.sh requires at least a URL to a conf file"
  echo "call_puddle.sh conf-url [PUDDLE_OPTS]"
  echo "All other passed paramters will be given directly to puddle"
  exit 1
fi

CONF_FILE=$(mktemp)
curl -o "${CONF_FILE}" "${1}"

shift

cat "${CONF_FILE}"

puddle "${CONF_FILE}" $@

rm "${CONF_FILE}"
