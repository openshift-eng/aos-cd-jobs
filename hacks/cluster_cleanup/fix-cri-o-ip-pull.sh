#!/bin/bash

if [ -z "$1" ]; then
        echo "Specify the IP address of the internal docker registry (e.g. '172.30.17.124')"
        echo "For reference, the IP should be listed below:"
        openssl s_client -showcerts -connect docker-registry.default.svc:5000 | openssl x509 -text | grep "DNS:docker-registry.default.svc"
        echo
        exit 0
fi

set -e
set -o xtrace

nodes=$(oc get nodes -l runtime=cri-o -o=name | cut -d / -f 2)

for node in $nodes ; do
        echo $node
        ssh -o StrictHostKeyChecking=no $node "ln -sfn /etc/docker/certs.d/docker-registry.default.svc:5000 /etc/docker/certs.d/$1:5000"
done
