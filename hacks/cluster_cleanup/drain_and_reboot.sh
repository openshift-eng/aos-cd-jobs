#!/usr/bin/env bash



types="$1"

if [ "$types" == "" ]; then
    echo "Syntax: $(basename $0) master,infra,compute  cluster1 [cluster2 ... clusterN]"
    exit 1
fi

shift

clusters="$@"

if [[ "$clusters" == "" ]]; then
        echo "Cluster ids required"
        exit 1
fi

echo "You must put clusters into maintenance before you begin"
read -p "Press enter to continue"

set -e
set -o xtrace

function wait_on_host() {
    try=0
    host=$1
    echo "Waiting for host to come online: ${host}"
    while ! timeout 1m autokeys_loader ssh root@${host} echo hello ; do
        sleep 30
        try=$((try + 1))
        if [ "${try}" == "20" ]; then
            echo "Timeout waiting for $host to come back online"
            exit 1
        fi
    done
    sleep 30 # Give it 30 more seconds to get right with the world
    return 0
}

for cluster in $clusters ; do
        master=$(ossh --list | grep "$cluster-master-" | head -n 1 | cut -d ' ' -f 1)
        master_cmd="autokeys_loader ssh -o StrictHostKeyChecking=no root@$master"

        if [[ $types = *"compute"* ]]; then
            nodes=$($master_cmd 'oc get nodes -l type=compute -o=name | cut -d / -f 2')

            for node in $nodes; do
                    echo "Working on $cluster : compute : $node"
                    $master_cmd "oc adm manage-node --schedulable=false $node"
                    $master_cmd "timeout 1h oc adm drain --delete-local-data --force --ignore-daemonsets $node" || true
                    tower_node=$($master_cmd "oc get node $node -L hostname | grep -v HOSTNAME | awk '{print \$6}'")

                    # cri-o nodes have no hostname
                    if [ ! -z "$tower_node" ]; then
                            autokeys_loader ssh -o StrictHostKeyChecking=no root@$tower_node "reboot" || true
                            echo "Waiting for COMPUTE node to reboot before moving on"
                            wait_on_host $tower_node
                    fi
                    
                    $master_cmd "oc adm manage-node --schedulable=true $node"
            done
        fi

        if [[ $types = *"infra"* ]]; then
            nodes=$($master_cmd 'oc get nodes -l type=infra -o=name | cut -d / -f 2')

            for node in $nodes; do
                    echo "Working on $cluster : infra : $node"
                    $master_cmd "oc adm manage-node --schedulable=false $node"
                    $master_cmd "timeout 1h oc adm drain --delete-local-data --force --ignore-daemonsets $node" || true
                    tower_node=$($master_cmd "oc get node $node -L hostname | grep -v HOSTNAME | awk '{print \$6}'")

                    # cri-o nodes have no hostname
                    if [ ! -z "$tower_node" ]; then
                            autokeys_loader ssh -o StrictHostKeyChecking=no root@$tower_node "reboot" || true
                    fi
                    $master_cmd "oc adm manage-node --schedulable=true $node"

                    echo "Waiting for INFRA node to reboot before moving on"
                    wait_on_host $tower_node
            done
        fi

        if [[ $types = *"master"* ]]; then
            masters=$(ossh --list | grep "$cluster-master-" | cut -d ' ' -f 1)

            for master in $masters; do
                    echo "Working on $cluster : master : $master"
                    autokeys_loader ssh -o StrictHostKeyChecking=no root@$master "reboot" || true
                    wait_on_host $master
            done
        fi

done
