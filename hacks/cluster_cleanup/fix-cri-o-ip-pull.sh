#!/bin/bash

set -e
set -o xtrace

reg_ip=$(dig +short docker-registry.default.svc.cluster.local)

nodes=$(oc get nodes -l runtime=cri-o -o=name | cut -d / -f 2)

for node in $nodes ; do
        echo $node
        ssh -o StrictHostKeyChecking=no $node "ln -sfn /etc/docker/certs.d/docker-registry.default.svc:5000 /etc/docker/certs.d/$reg_ip:5000"
done
