#!/bin/bash

set -o errexit   # All non-zero statuses will terminate script
set -o pipefail  # All components of piped command will terminate script if they fail
set -o nounset   # Makes substituting unset variables an error

## Need kerberos credential
kinit -k -t $KEYTAB $PRINCIPLE
task_number="$( tito release --yes --test "aos-${ose_version}" | grep 'Created task:' | awk '{print $3}' )"
brew watch-task "${task_number}"

# RPMs are now built, on to the images
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf -n -s --label=building"
ose_images.sh update_docker --branch "rhaos-${ose_version}-rhel-7" --group base --force --release 1 --version "${VERSION}"
ose_images.sh build_container --branch "rhaos-${ose_version}-rhel-7" --group base --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-building.repo
sudo ose_images.sh push_images --branch "rhaos-${ose_version}-rhel-7" --group base   # Requires docker permissions
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf"
# Script needs access to vagrant key
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "/mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors.sh simple ${ose_version}"

