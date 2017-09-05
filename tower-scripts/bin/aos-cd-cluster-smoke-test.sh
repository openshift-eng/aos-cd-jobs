#!/usr/bin/env bash

if [ "$#" -ne 1 ]
then
  echo "Usage: `basename $0` <clusterid>"
  exit 1
fi

CLUSTERNAME="$1"

MASTER=$(ansible "oo_clusterid_${CLUSTERNAME}:&oo_version_3:&oo_master_primary" --list-hosts | tail -1 | sed 's/ //g')
if [[ ${MASTER} != ${CLUSTERNAME}* ]]; then
    # Detect if cluster master was found
    echo "No cluster detected"
    exit 0
fi

WARNINGS=0

#
# Check for nodes that are not ready or unschedulable
#
ossh "root@${MASTER}" -c "/bin/bash" << EOF
set -e
if oc get nodes -l type=compute | grep -e SchedulingDisabled -e NotReady; then
    echo "WARNING: One or more compute nodes are SchedulingDisabled or NotReady"
    exit 1
fi

if oc get nodes -l type=infra | grep -e SchedulingDisabled -e NotReady; then
    echo "WARNING: One or more infrastructure nodes are SchedulingDisabled or NotReady"
    exit 1
fi
EOF

if [ "$?" != "0" ]; then
    WARNINGS=1
fi

#
# Check availability of infrastructure pods
#
# Escape \$ when the variable is designed to evaluate on the cluster as opposed to local host
for special_ns in default openshift-infra ; do
    ossh "root@${MASTER}" -c "/bin/bash" << EOF
    set -e

    for rc in \$(oc get rc -o=name -n $special_ns); do
        COUNT=\$(oc get \$rc --template={{.status.replicas}} -n $special_ns)
        READY=\$(oc get \$rc --template={{.status.readyReplicas}} -n $special_ns)
        # If COUNT==0, then READY is not defined
        if [ "\$COUNT" != "0" -a "\$COUNT" != "\$READY" ]; then
            oc get rc -n $special_ns
            echo "WARNING: In project $special_ns RC \$rc does not have all replicas satisfied (\$COUNT vs \$READY)"
            exit 1
        fi
    done
# Note the EOF cannot be indented
EOF
done

if [ "$?" != "0" ]; then
    WARNINGS=1
fi

#
# Check end user workflow by creating a simple app
#
# Using 'EOF' allows you to avoid escaping all uses of $
ossh "root@${MASTER}" -c "/bin/bash" << 'EOF'
    set -ex
    wait_for () {
        # wait until "oc get" succeeds for an object
        command="oc get $@"

        ATTEMPTS=5
        DELAY=10

        count=0
        until $command || [ $count -ge $ATTEMPTS ]; do
          sleep $DELAY
          count=$((count + 1))
        done
        if [ $count -ge $ATTEMPTS ]; then exit 1; fi
    }
    PROJ_RANDOM=aos-cd-smoketest-$(shuf -i 100000-999999 -n 1)
    oc new-project ${PROJ_RANDOM}
    wait_for project ${PROJ_RANDOM}
    oc new-app --image-stream=ruby --code=https://github.com/openshift/ruby-hello-world
    wait_for build ruby-hello-world-1
    oc expose svc/ruby-hello-world
    wait_for route ruby-hello-world
    timeout 10m oc logs -f bc/ruby-hello-world
    timeout 10m oc rollout status dc/ruby-hello-world
    wait_for endpoints ruby-hello-world
    sleep 30 # Give time to the router to sync route/endpoints
    curl --fail -Is $(oc get routes ruby-hello-world --template={{.spec.host}})
    oc delete project ${PROJ_RANDOM}
EOF

if [ "$?" != "0" ]; then
    echo "WARNING: Error deploying or accessing smoke-test application"
    WARNINGS=1
fi

exit $WARNINGS
