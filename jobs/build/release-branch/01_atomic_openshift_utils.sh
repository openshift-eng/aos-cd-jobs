#!/bin/bash
set -euo pipefail

cd /data/src/github.com/openshift/aos-cd-jobs/
pkg_name="origin"
echo $pkg_name > PKG_NAME
echo "openshift-ansible openshift-ansible-callback-plugins openshift-ansible-docs openshift-ansible-filter-plugins openshift-ansible-lookup-plugins openshift-ansible-playbooks openshift-ansible-roles" > OPENSHIFT_ANSIBLE_PKGS
sudo python sjb/hack/determine_install_upgrade_version.py $( cat OPENSHIFT_ANSIBLE_BUILT_VERSION ) --dependency_branch master > OPENSHIFT_ANSIBLE_VARS
source OPENSHIFT_ANSIBLE_VARS
versioned_packages_to_install=""
if [[ ${ATOMIC_OPENSHIFT_UTILS_INSTALL_MINOR_VERSION} -le 4 ]]
then
  sudo yum erase -y ansible
  versioned_packages_to_install="ansible-2.2.0.0"
fi
packages_to_install=( $( cat ./OPENSHIFT_ANSIBLE_PKGS ) )
for pkg in "${packages_to_install[@]}"
do
  versioned_packages_to_install+=" ${pkg}-${ATOMIC_OPENSHIFT_UTILS_INSTALL_VERSION}"
done
echo "=== Installing atomic-openshift-utils-${ATOMIC_OPENSHIFT_UTILS_INSTALL_VERSION} packages ==="
sudo yum install -y ${versioned_packages_to_install}
