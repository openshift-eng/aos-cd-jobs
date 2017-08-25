#!/bin/bash
set -o xtrace

if [ "$#" -ne 2 ]; then
  echo "Missing arguments."
  echo "Usage: sign_rpms.sh <brew_tag> <sig_name>"
  echo "Signature names available here: https://code.engineering.redhat.com/gerrit/gitweb?p=rhtools.git;a=blob;f=src/signing.py;hb=HEAD"
  exit 1
fi

TAG=${1}
KEY=${2}
BASE_TAG=`echo "${TAG}" | rev | cut -d '-' -f2- | rev`
echo ${BASE_TAG}

signdir=$(mktemp -d)

builds=$(brew list-tagged --latest --inherit --quiet ${TAG} | awk '{print $1}')
echo $builds

sign_script_path="/mnt/redhat/scripts/rel-eng/utility/sign_unsigned.py"
if [ ! -f "${sign_script_path}" ]; then
   echo "Unable to find rel-eng script: ${sign_script_path} . Make sure the tools drive is mounted."
   echo "In fstab: ntap-bos-c01-eng01-nfs01b.storage.bos.redhat.com:/devops_engineering_nfs/devarchive/redhat /mnt/redhat nfs tcp,ro,nfsvers=3 0 0"
   exit 1
fi

"${sign_script_path}" \
	--workdir="${signdir}" \
	--level="${KEY}" \
	--exact --write-rpms \
	--builds ${builds}
