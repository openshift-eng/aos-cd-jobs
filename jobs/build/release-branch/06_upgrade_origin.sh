#!/bin/bash
set -euo pipefail

cd /data/src/github.com/openshift/aos-cd-jobs/
pkg_name=$( cat ./PKG_NAME )
source ORIGIN_VARS
upgrade_playbook="/usr/share/ansible/openshift-ansible/playbooks/byo/openshift-cluster/upgrades/v3_${ORIGIN_UPGRADE_RELEASE_MINOR_VERSION}/upgrade.yml"
ansible-playbook  -vv                    \
                  --become               \
                  --become-user root     \
                  --connection local     \
                  --inventory sjb/inventory/ \
                   "${upgrade_playbook}"     \
                  -e etcd_data_dir=/tmp/etcd \
                  -e openshift_pkg_version="-${ORIGIN_UPGRADE_RELEASE_VERSION}" \
                  -e deployment_type=$( cat ./DEPLOYMENT_TYPE) \
                  -e oreg_url='openshift/origin-\${component}:'"$( cat ./ORIGIN_COMMIT )"
cd /data/src/github.com/openshift/origin/
origin_package="$( source hack/lib/init.sh; os::build::rpm::format_nvra )"
rpm -V "${origin_package}"
