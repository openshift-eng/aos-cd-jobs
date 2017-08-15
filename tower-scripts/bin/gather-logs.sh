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
MASTER_SERVICES="atomic-openshift-master-api atomic-openshift-master-controllers etcd"
NODE_SERVICES="docker atomic-openshift-node dnsmasq openvswitch ovs-vswitchd ovsdb-server"

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
PRIMARY_MASTER=$(ansible "oo_clusterid_${CLUSTERNAME}:&oo_version_3:&oo_master_primary" --list-hosts | tail -1 | sed 's/ //g')

info() {
    >&2 echo "INFO: $1"
}

warn() {
    >&2 echo "WARNING: $1"
}

# Translate an OpenShift node name to its inventory hostname, e.g.
# ip-172-31-69-53.us-east-2.compute.internal -> free-stg-node-infra-70a4e
inventory_name() {
    node_name=$1

    # Allow direct specification of the node's inventory name
    # (i.e. no translation needed)
    # NOTE/TODO: specifying nodes via their inventory name prevents collection
    # of data that depends on the node name (e.g. node metrics).
    if (echo "${ALL_CLUSTER_NODES}" | grep -Eo "^$node_name\s"); then
	return
    fi

    # extract IP from the node name, e.g
    # ip-172-31-69-53.us-east-2.compute.internal -> 172.31.69.53
    node_ip=$(echo $node_name | cut -d\. -f1 | sed -e 's/-/./g' -e 's/ip.//')

    # find the node's inventory name from its IP
    echo "${ALL_CLUSTER_NODES}" | grep $node_ip | awk '{print $1}'
}

# Collect information from masters
do_masters() {
    info "collecting information from masters"

    mkdir -p masters/reports

    for service in $MASTER_SERVICES; do
        info "gathering logs for '$service'"
        autokeys_loader opssh -c "$CLUSTERNAME" --v3 -t master --outdir masters/journal/$service "journalctl --no-pager --since '2 days ago' -u $service.service"
    done

    # TODO: return logs from failed deployments
    info "gathering node list and metrics"
    autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc get node" > masters/reports/nodes.txt
    autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc get --raw /metrics" > masters/reports/metrics.txt
}

# Collect information from one node
do_node() {
    node=$1

    # NOTE/TODO: specifying nodes via their inventory name prevents collection
    # of data that depends on the node name (e.g. node metrics).
    invnode=$(inventory_name $node)
    if [ -z $invnode ]; then
	# unknown node / not part of this cluster
	warn "unknown node '$node', ignoring"
	return
    fi

    info "collecting information from node '$node'"
    outdir="nodes/$node"
    mkdir -p "${outdir}/journal"

    # Gather logs from node services
    for service in $NODE_SERVICES; do
        info "gathering logs for '$service'"
        autokeys_loader ossh root@$invnode -c "journalctl --since '2 days ago' -u ${service}.service" > $outdir/journal/$service
    done
    # Gather metrics for the node
    # NOTE/TODO: this fails if the node was specified via its ansible inventory name
    info "gathering node info and metrics"
    autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc get --raw /api/v1/nodes/${node}/proxy/metrics" > $outdir/metrics.txt
    autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc describe node ${node}" > $outdir/describe.txt
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
