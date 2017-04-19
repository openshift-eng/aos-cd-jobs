#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

if [[ -n "$( git status --porcelain 2>&1 )" ]]; then
    echo "[FATAL] Cannot run this without a clean git state. Commit your changes and try again."
    exit 1
fi

if [[ -n "$( git diff HEAD~1..HEAD --stat -- generated/ )" ]]; then
    updated_jobs=( $( git diff HEAD~1..HEAD --numstat -- generated/ | awk '{ print $3 }' ) )
    ./push-update.sh "${updated_jobs[@]}"
fi