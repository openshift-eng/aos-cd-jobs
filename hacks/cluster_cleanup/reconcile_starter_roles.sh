#!/bin/bash -e

# This script is designed to bring the current roles up to date without 
# re-enabling scheduledjob/cronjob/custom-host creation on the starter clusters.

set -o xtrace

# Create a file that has all desired bootstrap policies
F0="/tmp/reconcile_roles.tmp"
oc adm create-bootstrap-policy-file --filename=$F0

# Filter the template to include only roles that feed into admin/edit/view that we care about.
# admin/edit/view were used on 3.7; the other roles are for when the cluster is using aggregation (e.g. 3.9).
F="/tmp/reconcile_roles.cleaned"
cat $F0 | jq '.objects = (.objects | 
                map(    select( .kind=="ClusterRole" and (
                                  .metadata.name=="system:aggregate-to-admin" or
                                  .metadata.name=="system:aggregate-to-edit" or
                                  .metadata.name=="system:aggregate-to-view" or
                                  .metadata.name=="system:openshift:aggregate-to-admin" or
                                  .metadata.name=="system:openshift:aggregate-to-edit" or
                                  .metadata.name=="system:openshift:aggregate-to-view" or
                                  .metadata.name=="admin" or
                                  .metadata.name=="edit" or
                                  .metadata.name=="view" 
                                )
                        )
                )
        )' > $F


BACKUP=$HOME/moslasthope
D=$(date +%s)
mkdir -p $BACKUP
for r in clusterrole clusterrolebinding role rolebinding ; do
        oc get $r -o=yaml > $BACKUP/$r.$D.org.yaml
done

# Rename the dangerous resources to meaningless names in order to remove all permissions to create them.
sed -i 's;cronjobs;cicd-is-disabling-cronjobs;g' $F
sed -i 's;scheduledjobs;cicd-is-disabling-scheduledjobs;g' $F
sed -i 's;routes/custom-host;cicd-is-disabling-routes/custom-host;g' $F

oc process -f $F | oc replace -n openshift -f -

for r in clusterrole clusterrolebinding role rolebinding ; do
        oc get $r -o=yaml > $BACKUP/$r.$D.new.yaml
done

# annotate the resoruces to ensure the next master restart does not reconcile away our changes
for r in system:aggregate-to-admin system:aggregate-to-edit system:aggregate-to-view system:openshift:aggregate-to-admin system:openshift:aggregate-to-edit system:openshift:aggregate-to-view admin edit view ; do 
        oc annotate clusterrole $r openshift.io/reconcile-protect=true --overwrite || true
done


#apiVersion: rbac.authorization.k8s.io/v1
#kind: ClusterRole
#metadata:
#  name: system:openshift:cicd:aggregate-to-all-cronjobs-read-and-del
#  labels:
#    rbac.authorization.k8s.io/aggregate-to-admin: "true"
#    rbac.authorization.k8s.io/aggregate-to-edit: "true"
#rules:
#- apiGroups:
#  - batch
#  resources:
#  - cronjobs
#  verbs:
#  - get
#  - list
#  - watch
#  - delete
#  - deletecollection


#apiVersion: rbac.authorization.k8s.io/v1
#kind: ClusterRole
#metadata:
#  name: system:openshift:cicd:aggregate-to-all-cronjobs-read
#  labels:
#    rbac.authorization.k8s.io/aggregate-to-view: "true"
#rules:
#- apiGroups:
#  - batch
#  resources:
#  - cronjobs
#  verbs:
#  - get
#  - list
#  - watch

