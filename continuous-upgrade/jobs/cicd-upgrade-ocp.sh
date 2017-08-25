#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace
sudo yum --disablerepo=* --enablerepo=openshift-int,oso-rhui-rhel-server-releases update -y atomic-openshift-utils
cd /root/aos-cd-jobs/
sudo python sjb/hack/determine_install_upgrade_version.py "\$( rpm -qa atomic-openshift )" > AOS_VARS
source AOS_VARS
ansible-playbook  -vv                    \
                  --become               \
                  --become-user root     \
                  --inventory /root/cicd-byo-inventory \
                   "/usr/share/ansible/openshift-ansible/playbooks/byo/openshift-cluster/upgrades/v3_\${ATOMIC_OPENSHIFT_UPGRADE_RELEASE_MINOR_VERSION}/upgrade.yml" \
                  -e openshift_pkg_version="-\${ATOMIC_OPENSHIFT_UPGRADE_RELEASE_VERSION}" 

SCRIPT
chmod +x "${script}"
eval "$(ssh-agent -s)"
ssh-add ~jenkins/.ssh/cicd_cluster_key
ssh -A -o StrictHostKeyChecking=no -tt root@master1.cicd.openshift.com "ansible all -i /root/cicd-byo-inventory -m ping"
scp -o StrictHostKeyChecking=no   "${script}" root@master1.cicd.openshift.com:"${script}"
ssh -A -o StrictHostKeyChecking=no -tt root@master1.cicd.openshift.com "bash -l -c \"${script}\""
