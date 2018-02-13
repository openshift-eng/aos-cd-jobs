#!/bin/bash

# Procedure for https://bugzilla.redhat.com/show_bug.cgi?id=1472624#c29

echo "This script is designed to be run from one of the cluster masters; make sure you are there!"
read -p "Press enter to continue"

echo "Do not run this unless your cluster is docker only (no cri-o). Or you can enhance it to exclude cri-o nodes.."
read -p 

set -o xtrace
set -e
nodes=$(oc get nodes -l type=compute -o=name)

if [ "$nodes" == "" ]; then
        echo "No nodes found"
fi

for node in $nodes; do
        node=$(echo $node | cut -d / -f 2) #  node/xyz to "xyz"

        echo "Processing node: $node"
        oadm manage-node --schedulable=false "$node"
        oadm drain --delete-local-data --force --ignore-daemonsets "$node"
        ssh -o StrictHostKeyChecking=no "root@$node" "systemctl stop atomic-openshift-node"
        ssh -o StrictHostKeyChecking=no "root@$node" "systemctl stop docker"
        sleep 20  # Wait for docker to truly stop
        ssh -o StrictHostKeyChecking=no "root@$node" "/usr/bin/chattr -i /var/lib/docker/volumes || true"
        ssh -o StrictHostKeyChecking=no "root@$node" "mount | grep /var/lib/origin/openshift.local.volumes | cut -d ' ' -f 3 | xargs --no-run-if-empty umount"
        ssh -o StrictHostKeyChecking=no "root@$node" "rm -rf /var/lib/origin/openshift.local.volumes"
        ssh -o StrictHostKeyChecking=no "root@$node" "rm -rf /var/lib/docker"
        ssh -o StrictHostKeyChecking=no "root@$node" "rm -rf /var/lib/cni/networks"  # https://bugzilla.redhat.com/show_bug.cgi?id=1518912
        ssh -o StrictHostKeyChecking=no "root@$node" "ovs-vsctl del-br br0"   # eparis recommended
        ssh -o StrictHostKeyChecking=no "root@$node" "docker-storage-setup --reset"
        ssh -o StrictHostKeyChecking=no "root@$node" "docker-storage-setup"
        ssh -o StrictHostKeyChecking=no "root@$node" "mkdir -p /var/lib/docker/volumes"  # An ops chattr drop in requires this

        ssh -o StrictHostKeyChecking=no "root@$node" "systemctl start docker"
        ssh -o StrictHostKeyChecking=no "root@$node" "systemctl start atomic-openshift-node"

        oadm manage-node --schedulable "$node"

done
