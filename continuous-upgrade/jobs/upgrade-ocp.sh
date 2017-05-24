#!/bin/bash
script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

sudo yum --disablerepo=* --enablerepo=openshift-int,oso-rhui-rhel-server-releases update -y atomic-openshift-utils
cd /data/src/github.com/openshift/aos-cd-jobs/
rpm -qa atomic-openshift
sudo python sjb/hack/determine_install_upgrade_version.py "\$( rpm -qa atomic-openshift )" > AOS_VARS
source AOS_VARS
ansible-playbook  -vv                    \
                  --become               \
                  --become-user root     \
                  --connection local     \
                  --inventory sjb/inventory/ \
                   "/usr/share/ansible/openshift-ansible/playbooks/byo/openshift-cluster/upgrades/v3_${ATOMIC_OPENSHIFT_UPGRADE_RELEASE_MINOR_VERSION=6}/upgrade.yml"     \
                  -e etcd_data_dir="/tmp/etcd" \
                  -e openshift_pkg_version="-\${ATOMIC_OPENSHIFT_UPGRADE_RELEASE_VERSION}" \
                  -e deployment_type="openshift-enterprise" \
                  -e oreg_url='registry.ops.openshift.com/openshift3/ose-\${component}:\${version}' \
                  -e openshift_docker_insecure_registries="brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888" \
                  -e openshift_docker_additional_registries="brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888,registry.ops.openshift.com"

SCRIPT
chmod +x "${script}"
scp -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config "${script}" openshiftdevel:"${script}"
ssh -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config -t openshiftdevel "bash -l -c \"${script}\""