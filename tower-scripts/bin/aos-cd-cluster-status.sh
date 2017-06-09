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

DOCKER_VERSION=$(ossh root@${MASTER} -c "rpm -q --qf %{VERSION}-%{RELEASE} docker")
OC_VERSION=$(ossh root@${MASTER} -c "oc version | head -1" | awk '{ print $2 }')
KUBE_VERSION=$(ossh root@${MASTER} -c "oc version | tail -1" | awk '{ print $2 }')
NETWORK_PLUGIN=$(ossh root@${MASTER} -c "grep networkPluginName /etc/origin/master/master-config.yaml" | awk '{ print $2 }')
METRICS_VERSION=$(ossh root@${MASTER} -c "oc get rc/hawkular-metrics -n openshift-infra  -o yaml | grep 'image:' | sed 's/.*://' | head -1" 2>/dev/null)
LOGGING_VERSION=$(ossh root@${MASTER} -c "oc get dc/logging-kibana -n logging  -o yaml | grep 'image:' | sed 's/.*://' | head -1" 2>/dev/null)
ONLINE_VERSION=$(ossh root@${MASTER} -c "rpm -qa | grep openshift-scripts | head -n 1" 2> /dev/null)


if [[ -z $METRICS_VERSION ]]; then
    METRICS_VERSION="None"
fi

if [[ -z $LOGGING_VERSION ]]; then
    LOGGING_VERSION="None"
fi

if [[ -z $ONLINE_VERSION ]]; then
    ONLINE_VERSION="None"
fi

get_kernels() {
# This is messy :D
    kernels=$(ansible -u root "oo_clusterid_${CLUSTERNAME}:&oo_version_3" -m shell -a "uname -r" | sed 's/ |.*//')
    kern_array=($kernels)

    printf "%-40s | %-30s\n" "Host" "Kernel"
    for i in $(seq 0 $((${#kern_array[@]}-1))); do
        if [[ $((i%2)) -eq 0 ]]; then
            printf "%-40s | %-30s\n" "${kern_array[i]}" "${kern_array[i+1]}"
        fi
    done
}

get_provisioner() {
    DYNAMIC_PROVISIONER=$(ossh root@${MASTER} -c "oc get storageclasses --no-headers 2>/dev/null" | grep default | awk '{ print $3 }')
    if [[ -z ${DYNAMIC_PROVISIONER} ]];
    then
        PV_POD_VERSION=$(ossh root@${MASTER} -c "oc get dc/online-volume-provisioner -n openshift-infra -o yaml | grep 'image:'" 2>/dev/null | sed 's/.*://')
        if [[ -z ${PV_POD_VERSION} ]]; then
            # NO dynamic provisioning
            echo "None (uses old style pre made PVs)"
        else
            echo "Provisioner Pod - Version ${PV_POD_VERSION}"
        fi
    else
        echo "Using storage class ${DYNAMIC_PROVISIONER}"
    fi
}

get_pods() {
    ossh root@${MASTER} -c "oc get pods -n $1"
}
 

echo -e "
Cluster Info:
    OC Version:      ${OC_VERSION}
    Online Version:  ${ONLINE_VERSION}
    API URL:         https://api.${CLUSTERNAME}.openshift.com
    Console URL:     https://console.${CLUSTERNAME}.openshift.com/console
    Docker Version:  ${DOCKER_VERSION}
    Kube Version:    ${KUBE_VERSION}
    Network Plugin:  ${NETWORK_PLUGIN}
    Metrics Version: ${METRICS_VERSION}
    Logging Version: ${LOGGING_VERSION}
    Provisioning:    $(get_provisioner)

Openshift Nodes:
$(ossh root@${MASTER} -c "oc get nodes")

Default Project Pods:
$(get_pods default)

OpenShift-Infra Project Pods:
$(get_pods openshift-infra)

Logging Project Pods:
$(get_pods logging)

Kernel Status:
$(get_kernels)

"

