#!/bin/bash
set -euxo pipefail

# Download conf file from URL and call puddle with given advisories

VERSION=$1
RHEL=${2:-el8}
CONF=`mktemp`
echo "Making new signed compose for OCP ${VERSION}-${RHEL}"

echo "Fetching default errata-puddle config file for ${VERSION}"
wget https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/puddle-conf/errata-puddle-${VERSION}-signed.${RHEL}.conf -O $CONF

echo "Running puddle command"
puddle $CONF -b -d -n
# "-b",   // do not fail if we are missing dependencies
# "-d",   // print debug information
# "-n"    // do not send an email for this puddle

echo "Cleaning up"
rm -vf $CONF

echo "Done"
