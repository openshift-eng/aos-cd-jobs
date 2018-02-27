#!/bin/bash -e

# This script is designed to bring the current roles up to date without 
# re-enabling scheduledjob/cronjob/custom-host creation on the starter clusters.

set -o xtrace

F="/tmp/reconcile_roles.tmp"

# Create a file that contains what all roles should be
oc adm create-bootstrap-policy-file --filename=$F

# Backup the current roles before updating them
BACKUP=$HOME/moslasthope
D=$(date +%s)
mkdir -p $BACKUP
for r in clusterrole clusterrolebinding role rolebinding ; do 
	oc get $r -o=yaml > $BACKUP/$r.$D.org.yaml
done

# Replace the disallowed resources with junk names so that they will no longer be honored
sed -i 's;cronjobs;cicd-is-disabling-cronjobs;g' $F
sed -i 's;scheduledjobs;cicd-is-disabling-scheduledjobs;g' $F
sed -i 's;routes/custom-host;cicd-is-disabling-routes/custom-host;g' $F

# Some of the roles that are included in the template don't exist on the cluster so
# replace fails to update them. However, the ones we care about are updated.
oc process -f $F | oc replace -n openshift -f - || true

# Capture copies of the new roles
for r in clusterrole clusterrolebinding role rolebinding ; do 
	oc get $r -o=yaml > $BACKUP/$r.$D.new.yaml
done

# Disable annotation of the roles. Otherwise, the next master restart will 
# reconcile them and lose our changes.
for r in system:aggregate-to-admin system:aggregate-to-edit system:aggregate-to-view system:openshift:aggregate-to-admin system:openshift:aggregate-to-edit system:openshift:aggregate-to-view admin edit view ; do 
	oc annotate clusterrole $r openshift.io/reconcile-protect=true --overwrite || true
done

# If anything was messed up by replace, restart a master and allow reconcile to correct it.
systemctl restart atomic-openshift-master-api
