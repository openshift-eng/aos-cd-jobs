#!/bin/bash
set -euxo pipefail

# Download conf file from URL and call puddle with given advisories

VERSION=$1
ERRATA=$2
CONF=`mktemp`

echo "Fetching default errata-puddle config file for ${VERSION}"
wget https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/puddle-conf/errata-puddle-${VERSION}-signed.conf -O $CONF

echo "Substituting in errata_whitelist with provided value: ${ERRATA}"
sed -i -r "s|errata_whitelist.*|errata_whitelist = ${ERRATA}|" $CONF

echo "Running puddle command"
puddle $CONF -b -d -n
# "-b",   // do not fail if we are missing dependencies
# "-d",   // print debug information
# "-n"    // do not send an email for this puddle

echo "Cleaning up"
rm -vf $CONF

echo "Done"
