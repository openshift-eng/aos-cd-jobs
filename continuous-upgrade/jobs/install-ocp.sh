script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

cat << EOR > ./openshift-int.repo
[openshift-int]
baseurl = https://mirror.openshift.com/enterprise/online-int/latest/x86_64/os/
enabled = 1
gpgcheck = 0
gpgkey = https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted
name = OpenShift Enterprise int Builds
sslclientcert = /var/lib/yum/client-cert.pem
sslclientkey = /var/lib/yum/client-key.pem
sslverify = 0
EOR
sudo cp ./openshift-int.repo /etc/yum.repos.d

sudo yum --disablerepo=* --enablerepo=openshift-int,oso-rhui-rhel-server-releases install -y atomic-openshift-utils
cd /data/src/github.com/openshift/aos-cd-jobs/
git pull origin master
/data/src/github.com/openshift/aos-cd-jobs/continuous-upgrade/actions/install_junit.sh
sudo yum-config-manager --disable rhel-7-server-ose-3\*,li
ansible-playbook  -vv          \
          --become           \
          --become-user root \
          --connection local \
          --inventory sjb/inventory/ \
          /usr/share/ansible/openshift-ansible/playbooks/byo/config.yml \
          -e etcd_data_dir="/tmp/etcd"                                  \
          -e deployment_type="openshift-enterprise"                     \
          -e oreg_url='registry.ops.openshift.com/openshift3/ose-\${component}:\${version}' \
          -e openshift_docker_insecure_registries="brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888" \
          -e openshift_docker_additional_registries="brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888,registry.ops.openshift.com"
sudo yum-config-manager --enable rhel-7-server-ose-3\*,li
SCRIPT
chmod +x "${script}"
scp -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config "${script}" openshiftdevel:"${script}"
ssh -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config -t openshiftdevel "bash -l -c \"${script}\""