#!/usr/bin/env bash
SCRIPT_DIR="$( cd "$( dirname "${0}" )" && pwd )"
OUTPUT_NEW="${1}/new_snapshot.txt"
OUTPUT_LAST="${1}/last_snapshot.txt"

if [ ! -f "${OUTPUT_LAST}" ]; then
    touch "${OUTPUT_LAST}" # make an empty file to diff against
fi

${SCRIPT_DIR}/gen_snapshot.sh > "${OUTPUT_NEW}"

# Following must be the only thing to output to stdout
diff "${OUTPUT_LAST}" "${OUTPUT_NEW}"

# copy new to last for next time
cp -f "${OUTPUT_NEW}" "${OUTPUT_LAST}"

