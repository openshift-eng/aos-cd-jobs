#!/bin/bash
#
# Download conf file from URL and call puddle
# Allows keeing all conf files in git and calling directly
# call_puddle.sh [CONF_FILE_URL] [SIGNED_KEYS]
# SIGNED_KEYS is optional and should be in the format "<key>,<key>,<key>" with no spaces
#

# set -o xtrace
set -e

usage()
{
cat<<EOF
  usage: ${0} --conf <conf_url> --keys <sig_keys|optional> [puddle opts]
  Options:
    --conf <conf_url> URL of puddle conf file to load. Required.
    --keys <sig_keys> Optional. Comma separated signature keys for RPMs to load into puddle.
    puddle opts: Required. Any options required by puddle will be passed to that command.
EOF
}

CONF_FILE_URL=
SIGNED_KEYS=

while [[ "$#" -ge 1 ]];
do
    case "${1}" in
      --conf)
        echo "CONF"
        CONF_FILE_URL="$2"
        shift 2;;
      --keys)
        echo "KEYS"
        SIGNED_KEYS="$2"
        shift 2;;
      *)
        break
        echo "OTHER: ${1}";;
   esac
done

if [[ -z ${CONF_FILE_URL} ]]; then
  echo "Must provide puddle conf URL!"
  usage
  exit 1
fi

if [[ "$#" -eq 0 ]]; then
  echo "Must provide options to pass to puddle!"
  usage
  exit 1
fi


CONF_TEMPLATE=$(mktemp)
curl -o "${CONF_TEMPLATE}" "${CONF_FILE_URL}"

if [ -n "${SIGNED_KEYS}" ]; then
  CONF_FILE=$(mktemp)
  echo "$(grep "(keys[ \t]*=[ \t]*)\|(signed[ \t]*=[ \t]*)" --invert-match "${CONF_TEMPLATE}")" > "${CONF_FILE}"
  echo "signed = yes" >> "${CONF_FILE}"
  echo "keys = ${SIGNED_KEYS}" >> "${CONF_FILE}"
else
  CONF_FILE="${CONF_TEMPLATE}"
fi

cat "${CONF_FILE}"

puddle "${CONF_FILE}" "$@"

rm "${CONF_TEMPLATE}"
rm "${CONF_FILE}"
