#!/bin/sh
# This script bumps version in a RPM specfile present in the working directory.
# It takes a version argument and that version is than used to override the old one.
#
# Usage:
#  ./rpm-bump-version 1.0.0
NEW=$1
SPEC=`ls *spec`

sed -i -e "s/Version:\([ ]*\).*/Version:\1$NEW/g" "$SPEC"
sed -i -e "s/Release:\([ ]*\).*/Release:\11%{?dist}/g" "$SPEC"

CHANGELOG='* '
CHANGELOG+=`date +'%a %b %d %Y'`
CHANGELOG+=" Justin Pierce <jupierce@redhat.com> - $NEW-1\n"
CHANGELOG+="- Update to $NEW"

sed -i -e "s/%changelog/%changelog\n$CHANGELOG\n/g" "$SPEC"
