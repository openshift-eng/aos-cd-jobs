#!/bin/bash
set -euxo pipefail

BREWLOGS=`find artcd_working -name brew-logs -type d`


if [ -s "${BREWLOGS}" ]; then
    echo "Brew logs (${BREWLOGS}) currently taking space:"
    du -sh $BREWLOGS
else
    echo "No brew logs found"
    exit 0
fi


tar -cjf brew-logs.tar.bz2 ${BREWLOGS}
tar -tf brew-logs.tar.bz2
mv brew-logs.tar.bz2 artcd_working/doozer_working/brew-logs.tar.bz2
rm -rf $BREWLOGS

echo "Compressed brew logs:"
ls -lh artcd_working/doozer_working/brew-logs.tar.bz2
