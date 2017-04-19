#!/bin/bash
#
# Find all the new packages that are in the simple puddle
#  And put them into the errata builds
#
############
# VARIABLES
############
#VERSION="3.5"
VERSION="${1}"
SIMPLELINK="building"
ERRATALINK="building"
BASEDIR="/mnt/rcm-guest/puddles/RHAOS"
SIMPLEDIR="${BASEDIR}/AtomicOpenShift/${VERSION}/${SIMPLELINK}/x86_64/os/Packages"
ERRATADIR="${BASEDIR}/AtomicOpenShift-errata/${VERSION}/${ERRATALINK}/RH7-RHAOS-${VERSION}/x86_64/os/Packages"
GITEXCLUDE="-e cockpit -e python-jsonschema -e python-ruamel-yaml -e python-wheel -e openshift-ansible -e atomic-openshift-clients-redistributable"

# Find out differences, put them in a file
echo
echo "Packages only in the simple puddle"
echo "----"
diff --brief -r ${SIMPLEDIR}/ ${ERRATADIR}/ | grep "${SIMPLEDIR}" | grep -v ${GITEXCLUDE} | awk '{print $4}' 
