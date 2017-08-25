#!/bin/bash
#
# Find all the new packages that are in the simple puddle
#  And put them into the errata builds
#
############
# VARIABLES
############
TMPDIR=$(mktemp -d /tmp/simple-to-errata-XXXXXX)
#VERSION="3.5"
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
comm -23 ${ERRATATMP} ${SIGNEDTMP} | while read line
do
  rpm -qp --qf "%{SOURCERPM}\n" ${ERRATADIR}/$line | rev | cut -d'.' -f3- | rev >> ${TMPDIR}/erratasourcerpm
done
if [ -s ${TMPDIR}/erratasourcerpm ] ; then
  sort -u -o ${TMPDIR}/erratasourcerpm ${TMPDIR}/erratasourcerpm
  cat ${TMPDIR}/erratasourcerpm
else
  echo "  No Differences"
fi
echo
echo "==== IN Signed Only ===="
comm -13 ${ERRATATMP} ${SIGNEDTMP} | while read line
do
  rpm -qp --qf "%{SOURCERPM}\n" ${SIGNEDDIR}/$line | rev | cut -d'.' -f3- | rev >> ${TMPDIR}/signedsourcerpm
done
if [ -s ${TMPDIR}/signedsourcerpm ] ; then
  sort -u -o ${TMPDIR}/signedsourcerpm ${TMPDIR}/signedsourcerpm
  cat ${TMPDIR}/signedsourcerpm
else
  echo "  No Differences"
fi
echo

# Cleanup
rm -f /tmp/${0}.{errata,signed}
