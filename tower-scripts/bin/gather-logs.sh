#!/usr/bin/env bash

if [ "$#" -ne 1 ]; then
	echo "Usage: `basename $0` <clusterid>"
	echo "Output will be a tarball of cluster logs. Do not pipe to stdout."
  	exit 1
fi

CLUSTERNAME="$1"
MASTER=$(ansible "oo_clusterid_${CLUSTERNAME}:&oo_version_3:&oo_master_primary" --list-hosts | tail -1 | sed 's/ //g')
BASEDIR=$(mktemp -p /tmp -d gather-logs.XXXXXXXX)

pushd "$BASEDIR" > /dev/null
	{
		for service in docker atomic-openshift-master-api atomic-openshift-master-controllers atomic-openshift-node; do
			outdir="journal/masters/$service"
			mkdir -p "$outdir"
			autokeys_loader opssh -c "$CLUSTERNAME" --v3 -t master --outdir "$outdir" 'journalctl --since "1 day ago" | tail --lines 200000'
		done

		mkdir -p "reports"
		autokeys_loader ossh "root@${MASTER}" -c "oc get pods --all-namespaces" > reports/pods.txt
		autokeys_loader ossh "root@${MASTER}" -c "oc status" > reports/status.txt
	} > "$BASEDIR/gather-logs.debug" 2>&1

	tar zcf - *

popd > /dev/null

rm -rf "${BASEDIR}"
