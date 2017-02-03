#!/bin/bash -e
#

#function print_usage() {
#  echo
#  echo "Usage: $(basename $0)<clusterid>"
#  echo "Examples:"
#  echo
#  echo "    $(basename $0) prod-cluster"
#  echo
#}

#if [ "$#" -ne 1 ]
#then
#  print_usage
#  exit 1
#fi

pushd ../git/openshift-ansible-ops/playbooks/release/decommission/
  autokeys_loader /usr/bin/ansible-playbook aws_remove_cluster.yml -e cli_clusterid=cicd -e cluster_to_delete=cicd -e run_in_automated_mode=True
popd
