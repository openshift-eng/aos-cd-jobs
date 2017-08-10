#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

# Get latest svt and aos-cd-jobs repos so the reliability test will run the latest changes
mv /root/svt/reliability/config/users.data /root/
rm -rf /root/svt /root/aos-cd-jobs
git clone https://github.com/openshift/aos-cd-jobs.git
git clone https://github.com/openshift/svt.git
cp -Rf /root/aos-cd-jobs/continuous-upgrade/reliability-test/tasks /root/svt/reliability/config/
cp -f /root/aos-cd-jobs/continuous-upgrade/reliability-test/config.yml /root/svt/reliability/config/
mv /root/users.data /root/svt/reliability/config/

cd /root/svt/reliability

# Check if users.data is empty. If it empty then the test is not running and its safe to run the playbook.
if [ ! -s /root/reliability/config/users.data ]; then
    ansible-playbook  -vvv                   \
                      --become               \
                      --become-user root     \
                      --inventory /root/cicd-byo-inventory \
                      "setup.yml"
fi

# Logrotate the reliability test log
if ! grep -q /root/svt/reliability/logs/reliability.log /etc/logrotate.conf; then
cat <<EOT >> /etc/logrotate.conf
/root/svt/reliability/logs/reliability.log {
        size 100k
}
EOT
fi

./reliabilityTests.sh start
SCRIPT
chmod +x "${script}"
eval "$(ssh-agent -s)"
ssh-add ~jenkins/.ssh/cicd_cluster_key
scp -o StrictHostKeyChecking=no   "${script}" root@master1.cicd.openshift.com:"${script}"
ssh -A -o StrictHostKeyChecking=no -tt root@master1.cicd.openshift.com "bash -l -c \"${script}\""
