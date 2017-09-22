#!/bin/bash

if [ "$1" == "" ]; then
	echo "Cluster name must be specified (e.g. starter-us-east-1)"
	exit 1
fi

CLUSTER="$1"

set -e

opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t node -i atomic-openshift-excluder unexclude
opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t node -i yum clean all 

nodes=$(ossh --list | grep "${CLUSTER}-node" | awk '{print $1}')

COUNT=0
IFS=$'\n'
for node in $nodes; do

	if [ "$(($COUNT % 10))" == "0" ]; then
		echo "  About to process batch $(($COUNT / 10))"
		read -p "   Press enter to continue"
	fi

	echo "Processing node: $node"
	ossh -o StrictHostKeyChecking=no "root@${node}" -c "sed -i '/^RestartSec/ s/$/\nTimeoutStartSec=300/' /etc/systemd/system/atomic-openshift-node.service"
	ossh -o StrictHostKeyChecking=no "root@${node}" -c "systemctl daemon-reload"
	ossh -o StrictHostKeyChecking=no "root@${node}" -c "yum upgrade -y atomic-openshift-node"
	ossh -o StrictHostKeyChecking=no "root@${node}" -c "systemctl restart atomic-openshift-node"
	
	COUNT=$((COUNT+1))
done


opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t node -i atomic-openshift-excluder exclude
