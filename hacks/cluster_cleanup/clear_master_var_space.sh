#!/bin/bash

# Cleans up space on /var so that openshift-ansible has space for etcd 
# backups.

CLUSTER="$1"
if [ "$1" == "" ]; then
	echo "Cluster must be specified (e.g. starter-us-east-1)"
	exit 1
fi

set -e
set -o xtrace

masters=$(ossh --list | grep "${CLUSTER}-master" | awk '{print $1}')

if [ "$masters" == "" ]; then
	echo "Unable to find masters"
	exit 1
fi

COUNT=0
IFS=$'\n'
for master in $masters ; do
	echo "Processing master: $master"
	# ossh -o StrictHostKeyChecking=no "root@${master}" -c "etcdctl3 defrag"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "rm -rf /var/lib/origin/core.*"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "rm -rf /var/lib/etcd/openshift-backup-*"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "rm -rf /var/cache/yum/*"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "rm -rf /var/log/*.gz"
	ossh -o StrictHostKeyChecking=no "root@${master}" -c "journalctl --vacuum-time=5h"
	COUNT=$((COUNT+1))
done
