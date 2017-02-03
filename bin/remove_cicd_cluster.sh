#!/bin/bash -e

pushd ../git/openshift-ansible-ops/playbooks/release/decommission/
  autokeys_loader /usr/bin/ansible-playbook aws_remove_cluster.yml -e cli_clusterid=cicd -e cluster_to_delete=cicd -e run_in_automated_mode=True
popd
