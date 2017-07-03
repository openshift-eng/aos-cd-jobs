#!/bin/bash
set -euo pipefail

cd /data/src/github.com/openshift/aos-cd-jobs/
pkg_name=$( cat ./PKG_NAME )
if [[ "${pkg_name}" == "origin" ]]; then
    deployment_type="origin"
elif [[ "${pkg_name}" == "atomic-openshift" ]]; then
    deployment_type="openshift-enterprise"
else
    echo "Can't determine deployment type"
    exit 1
fi
echo "${deployment_type}" > DEPLOYMENT_TYPE
sudo python sjb/hack/determine_install_upgrade_version.py \
  $( cat ORIGIN_BUILT_VERSION ) --dependency_branch master \
  > ORIGIN_VARS
source ORIGIN_VARS
source OPENSHIFT_ANSIBLE_VARS
echo "=== Installing ${pkg_name}-\${ORIGIN_INSTALL_VERSION} ==="
ansible-playbook  -vv                \
                  --become           \
                  --become-user root \
                  --connection local \
                  --inventory sjb/inventory/ \
                  /usr/share/ansible/openshift-ansible/playbooks/byo/openshift-node/network_manager.yml \
                  -e deployment_type=$( cat ./DEPLOYMENT_TYPE)
ansible-playbook  -vv                \
                  --become           \
                  --become-user root \
                  --connection local \
                  --inventory sjb/inventory/ \
                  /usr/share/ansible/openshift-ansible/playbooks/byo/config.yml \
                  -e openshift_pkg_version="-${ORIGIN_INSTALL_VERSION}"         \
                  -e etcd_data_dir=/tmp/etcd                                    \
                  -e deployment_type=$( cat ./DEPLOYMENT_TYPE)
