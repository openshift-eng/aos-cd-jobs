#!/usr/bin/env bash

if [ "$#" -ne 1 ]; then
  echo "Usage: `basename $0` <clusterid>"
  echo "Output will be a tarball of cluster logs. Do not pipe to stdout."
  exit 1
fi

# List of services that will be added to the download
MASTER_SERVICES="docker atomic-openshift-master-api atomic-openshift-master-controllers atomic-openshift-node"

# This will print out the contents of the $MASTER_SERVICES variable onto the same line
# with the _SYSTEMD_UNIT=<service>.service by turning them into an array,
# This will be useful in the future when we allow the selection to have all service logs collated
# in one file.
# This is unused for now.
MASTER_SERVICES_LIST=$(for i in ${!MASTER_SERVICES[@]}; do echo -n "_SYSTEMD_UNIT=${MASTER_SERVICES[i]}.service "; done)

######################
# GLOBAL VARS
CLUSTERNAME="$1"
PRIMARY_MASTER=$(ansible "oo_clusterid_${CLUSTERNAME}:&oo_version_3:&oo_master_primary" --list-hosts | tail -1 | sed 's/ //g')
BASEDIR=$(mktemp -p /tmp -d gather-logs.XXXXXXXX)

######################
# Begin Script
pushd "$BASEDIR" > /dev/null
    {
        for service in $MASTER_SERVICES; do
            outdir="journal/masters/$service"
            mkdir -p "$outdir"
            autokeys_loader opssh -c "$CLUSTERNAME" --v3 -t master --outdir "$outdir" 'journalctl --no-pager --since "2 days ago" _SYSTEMD_UNIT='"$service"'.service'
        done

        mkdir -p "reports"
        # TODO: make namespace configurable
        # TODO: return logs from failed deployments
        autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc get pods --all-namespaces" > reports/pods.txt
        autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc status -v --all-namespaces" > reports/status.txt
        autokeys_loader ossh "root@${PRIMARY_MASTER}" -c "oc get events --all-namespaces" > reports/events.txt
    } > "$BASEDIR/gather-logs.debug" 2>&1

    tar zcf - *

popd > /dev/null

rm -rf "${BASEDIR}"
