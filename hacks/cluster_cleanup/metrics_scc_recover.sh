#!/bin/sh

set -o xtrace
set -e

# get namespace SCC values
fsGroup=$(oc get ns openshift-infra -o template --template='{{index . "metadata" "annotations" "openshift.io/sa.scc.supplemental-groups"}}' | cut -d / -f 1)
uid=$(    oc get ns openshift-infra -o template --template='{{index . "metadata" "annotations" "openshift.io/sa.scc.uid-range"          }}' | cut -d / -f 1)
selinux=$(oc get ns openshift-infra -o template --template='{{index . "metadata" "annotations" "openshift.io/sa.scc.mcs"                }}')

echo $fsGroup
echo $uid
echo $selinux

rcs=$(oc get rc -n openshift-infra -o=name | grep hawkular-cassandra)

backup_dir=$HOME/metrics-patch-backup
mkdir -p $backup_dir

ts=$(date +%s)

for rc in $rcs ; do

        rc=$(echo $rc | cut -f 2 -d /)

        org="$backup_dir/original-$rc-$ts.json"
        mod="$backup_dir/modified-$rc-$ts.json"

        # store original
        oc get -n openshift-infra -o json rc/$rc | jq 'del(.metadata.resourceVersion)' > $org
        # modify
        cat $org | \
                jq ".spec.template.spec.containers[].securityContext |= . + {\"runAsUser\":$uid}" | \
                jq ".spec.template.spec.securityContext |= . + {\"fsGroup\":$fsGroup, \"seLinuxOptions\":{\"level\":\"$selinux\"}}" > $mod

        # replace
        oc replace -f $mod

done

# delete existing pods so that new rc will recover them
oc delete -n openshift-infra $(oc get pods -n openshift-infra -o=name | grep hawkular-cassandra-)
