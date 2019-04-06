#!/bin/bash

set -e
set -o xtrace

location="${1:-}"
log=$(mktemp)  # push.enterprise.sh does not indicate errors with rc so check output

timeout 2h /usr/local/bin/push.enterprise.sh reposync -v $location |& tee -a \$log

grep -q '\[FAILURE\]' $log && rc=1 || rc=0
rm -f $log
exit $rc
