#!/bin/bash

CLUSTER="$1"
if [ "$1" == "" ]; then
	echo "Cluster must be specified (e.g. starter-us-east-1)"
	exit 1
fi

set -e
set -o xtrace

opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t master -i atomic-openshift-excluder unexclude
opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t master -i yum clean all 

masters=$(ossh --list | grep "${CLUSTER}-master" | awk '{print $1}')

if [ "$masters" == "" ]; then
	echo "Unable to find masters"
	exit 1
fi

COUNT=0
IFS=$'\n'
for master in $masters ; do
	echo "Processing master: $master"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "yum upgrade -y atomic-openshift\*"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "systemctl restart atomic-openshift-master-api"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "systemctl restart atomic-openshift-master-controllers"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "systemctl restart atomic-openshift-node"
	
	COUNT=$((COUNT+1))
done


opssh -c $CLUSTER --v3 -O StrictHostKeyChecking=no -t master -i atomic-openshift-excluder exclude
