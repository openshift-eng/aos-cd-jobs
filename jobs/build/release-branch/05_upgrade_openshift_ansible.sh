#!/bin/bash
set -euo pipefail

cd /data/src/github.com/openshift/aos-cd-jobs/
source ORIGIN_VARS
source OPENSHIFT_ANSIBLE_VARS
versioned_packages_to_upgrade=""
packages_to_upgrade=( $( cat ./OPENSHIFT_ANSIBLE_PKGS ) )
for pkg in "${packages_to_upgrade[@]}"
do
  versioned_packages_to_upgrade+=" ${pkg}-${ATOMIC_OPENSHIFT_UTILS_UPGRADE_RELEASE_VERSION}"
done
sudo yum upgrade -y ${versioned_packages_to_upgrade}
cd /data/src/github.com/openshift/openshift-ansible/
last_tag="$( git describe --tags --abbrev=0 --exact-match HEAD )"
last_commit="$( git log -n 1 --pretty=%h )"
rpm -V "${last_tag}.git.0.${last_commit}.el7"
