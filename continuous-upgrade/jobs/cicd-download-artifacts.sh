scp -o StrictHostKeyChecking=no -r root@master1.cicd.openshift.com:/tmp/ansible_junit "${WORKSPACE}"
script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace
rm -rf "\${ANSIBLE_JUNIT_DIR}"/*
SCRIPT
chmod +x "${script}"
scp -o StrictHostKeyChecking=no "${script}" root@master1.cicd.openshift.com:"${script}"
ssh -A -o StrictHostKeyChecking=no -tt root@master1.cicd.openshift.com "bash -l -c \"${script}\""