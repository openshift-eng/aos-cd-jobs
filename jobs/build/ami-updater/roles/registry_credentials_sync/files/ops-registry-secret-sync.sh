#!/usr/bin/env bash

set -o pipefail

while true ; do
    echo "Attempt to read secret from cluster..."
    oc --config /etc/origin/node/node.kubeconfig -n openshift get secrets reg-aws-dockercfg -o=yaml | grep '.dockerconfigjson:' | cut -d ':' -f 2 | tr -d ' ' | base64 -d > /root/.docker/config.stg
    if [ "$?" == "0" ]; then
        # If there is a different between the staging and target
        if ! diff /root/.docker/config.stg /root/.docker/config.json > /dev/null; then
            # Use \cp to avoid aliases like cp -i.
            \cp /root/.docker/config.stg /root/.docker/config.json
            \cp /root/.docker/config.stg /var/lib/origin/.docker/config.json
            echo "Docker secrets updated. Will refresh again in 2 hours."
        else
            echo "Docker secrets are in sync. Will refresh again in 2 hours."
        fi
       sleep 2h
    else
        echo "Error reading secret from cluster; node.kubeconfig may not be up-to-date yet. Retrying in 30 seconds."
        sleep 30
    fi

done
