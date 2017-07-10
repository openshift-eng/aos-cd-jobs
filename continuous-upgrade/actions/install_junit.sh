#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

cd "/tmp"
sudo yum install -y python-pip
sudo pip install junit_xml
sudo chmod o+rw /etc/environment
echo "ANSIBLE_JUNIT_DIR=$( pwd )/ansible_junit" >> /etc/environment
export ANSIBLE_JUNIT_DIR="$( pwd )/ansible_junit"
echo "${ANSIBLE_JUNIT_DIR}"
mkdir -p "${ANSIBLE_JUNIT_DIR}"
sudo mkdir -p /usr/share/ansible/plugins/callback
for plugin in 'default_with_output_lists' 'generate_junit'; do
   wget "https://raw.githubusercontent.com/openshift/origin-ci-tool/master/oct/ansible/oct/callback_plugins/${plugin}.py"
   sudo mv "${plugin}.py" /usr/share/ansible/plugins/callback
done
sudo sed -r -i -e 's/^#?stdout_callback.*/stdout_callback = default_with_output_lists/' -e 's/^#?callback_whitelist.*/callback_whitelist = generate_junit/' /etc/ansible/ansible.cfg
