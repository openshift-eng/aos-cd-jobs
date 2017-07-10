scp -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config -r openshiftdevel:/tmp/ansible_junit "${WORKSPACE}"

script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace

rm -rf "${ANSIBLE_JUNIT_DIR}/*"

SCRIPT
chmod +x "${script}"
scp -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config "${script}" openshiftdevel:"${script}"
ssh -F ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config -t openshiftdevel "bash -l -c \"${script}\""