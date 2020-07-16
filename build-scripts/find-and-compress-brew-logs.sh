#!/bin/bash
set -euxo pipefail

BREWLOGS=`find . -name brew-logs -type d`


if [ -s "${BREWLOGS}" ]; then
    echo "Brew logs (${BREWLOGS}) currently taking space:"
    du -sh $BREWLOGS
else
    echo "No brew logs found"
    exit 0
fi


tar -cjf brew-logs.tar.bz2 ${BREWLOGS}
tar -tf brew-logs.tar.bz2
mv brew-logs.tar.bz2 doozer_working/brew-logs.tar.bz2
rm -rf $BREWLOGS

echo "Compressed brew logs:"
ls -lh doozer_working/brew-logs.tar.bz2
