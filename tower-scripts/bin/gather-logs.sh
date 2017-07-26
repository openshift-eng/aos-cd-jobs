#!/usr/bin/env bash

if [ "$#" -lt 1 ]; then
  echo "Usage: `basename $0` CLUSTERID [node]..."
  echo "Output will be a tarball of cluster logs. Do not pipe to stdout."
  exit 1
fi

CLUSTERNAME="$1"
shift
NODES="$@"

# List of services whose journal will be added to the download
MASTER_SERVICES="atomic-openshift-master-api atomic-openshift-master-controllers"
NODE_SERVICES="docker atomic-openshift-node"

# Prepare working environment
TMPDIR="${HOME}/aos-cd/tmp"
BASEDIR="logs-${CLUSTERNAME}-$(date +%Y%m%d%H%M)"
WORKDIR="${TMPDIR}/${BASEDIR}"
mkdir -p $WORKDIR
LOGFILE="${WORKDIR}/gather-logs.debug"

# Clean up before exit
on_exit() {
    rm -rf "${WORKDIR}"
}
trap on_exit EXIT

ALL_CLUSTER_NODES=$(ossh --list | grep "^${CLUSTERNAME}")

# Translate an OpenShift node name to its inventory hostname, e.g.
# ip-172-31-69-53.us-east-2.compute.internal -> free-stg-node-infra-70a4e
inventory_name() {
    node_name=$1

    # Allow direct specification of the node's inventory name
    # (i.e. no translation needed)
    if (echo $ALL_CLUSTER_NODES | grep -wo "^$node_name"); then
	return
    fi

    # extract ip from the node name, e.g
    # ip-172-31-69-53.us-east-2.compute.internal -> 172.31.69.53
    node_ip=$(echo $node_name | cut -d\. -f1 | sed -e 's/-/./g' -e 's/ip.//')

    # find the node's inventory name using its IP
    echo $ALL_CLUSTER_NODES | grep $node_ip | awk '{print $1}'
}

# Collect information from masters
do_masters() {
    for service in $MASTER_SERVICES; do
        outdir="journal/masters/$service"
        mkdir -p "$outdir"
        autokeys_loader opssh -c "$CLUSTERNAME" --v3 -t master --outdir "$outdir" 'journalctl --no-pager --since "2 days ago" _SYSTEMD_UNIT='"$service"'.service'
    done

    primary_master=$(ansible "oo_clusterid_${CLUSTERNAME}:&oo_version_3:&oo_master_primary" --list-hosts | tail -1 | sed 's/ //g')
    mkdir -p "reports"
    # TODO: make namespace configurable
    # TODO: return logs from failed deployments
    autokeys_loader ossh "root@${primary_master}" -c "oc get pods --all-namespaces" > reports/pods.txt
    autokeys_loader ossh "root@${primary_master}" -c "oc get events --all-namespaces" > reports/events.txt
}

# Collect information from one node
do_node() {
    node=$1

    invnode=$(inventory_name $node)
    if [ -z $invnode ]; then
	# unknown node / not part of this cluster
	>&2 echo "WARNING: unknown node '$node', ignoring"
	return
    fi
    for service in $NODE_SERVICES; do
        outdir="journal/nodes/$node"
        mkdir -p "$outdir"
        autokeys_loader ossh root@$invnode -c "journalctl --since '2 days ago' -u ${service}.service" > $outdir/$service
    done
}

######################
# Begin Script
pushd $WORKDIR > /dev/null
    {
	do_masters
	for node in $NODES; do
	    do_node $node
	done
    } > $LOGFILE

popd > /dev/null

tar zcf - -C $TMPDIR $BASEDIR
