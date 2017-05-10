#!/usr/bin/env bash

# During an upgrade, openshift-ansible needs to stop docker for a number of reasons.
# However, in Docker 1.12, there is an issue where a docker "cleanup" timer is executed
# every hour, on the hour. When it runs, it starts docker again and this interferes with
# openshift-ansible.
# Simply stopping this time is not an option since the docker service marks it as "Required"
# (i.e. stopping the timer brings down the docker services as well).
# So, we need to disable this timer safely for the duration of the install
# and then turn it back on.

if [ "$1" == "" ]; then
    echo "A cluster name must be specified"
    exit 1
fi

export CLUSTER_NAME="$1"

function restoreTimer {
    # Uncomment the Requires in docker.service if we have commented it out
    autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no 'sed -i "s/^#\(Requires=docker-cleanup.timer\)/\1/" /usr/lib/systemd/system/docker.service'
    autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no 'systemctl daemon-reload'
    autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no  "systemctl start docker-cleanup.timer"
}

# Reverse the changes when this script is terminated
trap restoreTimer EXIT

# Make it so that stopping the timer does not stop docker
autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no 'sed -i "s/^\(Requires=docker-cleanup.timer\)/#\1/" /usr/lib/systemd/system/docker.service'
# Load that change
autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no 'systemctl daemon-reload'

# Continuously disable the timer. This for clusters which are going from docker versions less than
# 1.12 to 1.12 during the upgrade
while true; do
    autokeys_loader opssh -c "${CLUSTER_NAME}" --v3 -O StrictHostKeyChecking=no "systemctl stop docker-cleanup.timer"
    sleep 60
done


