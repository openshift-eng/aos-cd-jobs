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

ossh "root@${MASTER}" -c "/bin/bash" << EOF
set -e
if oc get nodes -l type=compute | grep -e SchedulingDisabled -e NotReady; then
    echo "WARNING: One or more compute nodes are SchedulingDisabled or NotReady"
    exit 1
fi

if [ "$?" != "0" ]; then
    WARNINGS=1
fi

if oc get nodes -l type=infra | grep -e SchedulingDisabled -e NotReady; then
    echo "WARNING: One or more compute nodes are SchedulingDisabled or NotReady"
    exit 1
fi
EOF

if [ "$?" != "0" ]; then
    WARNINGS=1
fi

# Escape \$ when the variable is designed to evaluate on the cluster as opposed to local host
for special_ns in default openshift-infra ; do
    ossh "root@${MASTER}" -c "/bin/bash" << EOF
    set -e

    for rc in \$(oc get rc -o=name -n $special_ns); do
        COUNT=\$(oc get \$rc --template={{.status.replicas}} -n $special_ns)
        READY=\$(oc get \$rc --template={{.status.readyReplicas}} -n $special_ns)
        # If COUNT==0, then READY is not defined
        if [ "\$COUNT" != "0" -a "\$COUNT" != "\$READY" ]; then
            oc get rc
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

# Using 'EOF' allows you to avoid escaping all uses of $
ossh "root@${MASTER}" -c "/bin/bash" << 'EOF'
    set -e
    oc delete --ignore-not-found project aos-cd-smoke-test-proj
    sleep 60 # Allow project to be deleted
    oc new-project aos-cd-smoke-test-proj
    sleep 10  # Allow project to initialize
    oc new-app --image-stream=ruby --code=https://github.com/openshift/ruby-hello-world
    sleep 60  # Allow build to start
    timeout 10m oc logs -f bc/ruby-hello-world
    oc get pods | grep "Running"
    oc expose svc/ruby-hello-world
    sleep 10
    oc get routes
    curl $(oc get routes ruby-hello-world --template={{.spec.host}})
EOF

if [ "$?" != "0" ]; then
    echo "WARNING: Error deploying or accessing smoke-test application"
    WARNINGS=1
fi

exit $WARNINGS