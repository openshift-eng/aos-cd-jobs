#!/bin/bash
#
# Find all the new packages that are in the simple puddle
#  And put them into the errata builds
#
############
# VARIABLES
############
TMPDIR=$(mktemp -d /tmp/simple-to-errata-XXXXXX)
#VERSION="3.1"
VERSION="${1}"
ERRATALINK="building"
SIGNEDLINK="building"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
ERRATADIR="${BASEDIR}/AtomicOpenShift-errata/${VERSION}/${ERRATALINK}/RH7-RHAOS-${VERSION}/x86_64/os/Packages"
SIGNEDDIR="${BASEDIR}/AtomicOpenShift-signed/${VERSION}/${SIGNEDLINK}/RH7-RHAOS-${VERSION}/x86_64/os/Packages"
ERRATATMP="${TMPDIR}/errata"
SIGNEDTMP="${TMPDIR}/signed"

# Find out differences, put them in a file
ls -1 ${ERRATADIR}/ > ${ERRATATMP} 
ls -1 ${SIGNEDDIR}/ > ${SIGNEDTMP} 
sort -o ${ERRATATMP} ${ERRATATMP}
sort -o ${SIGNEDTMP} ${SIGNEDTMP}

echo "==== IN Errata Only ===="
comm -23 ${ERRATATMP} ${SIGNEDTMP}
echo
echo "==== IN Signed Only ===="
comm -13 ${ERRATATMP} ${SIGNEDTMP}
echo

# Cleanup
rm -f /tmp/${0}.{errata,signed}
