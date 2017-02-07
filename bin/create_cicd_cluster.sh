#!/bin/bash
#
set -euo pipefail

# Kill all background jobs on normal exit or signal
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

# Install ssh key to allow us to ssh locally
pushd ~/aos-cd/git/aos-cd-jobs/vars
  source private/setup_opstest_vars_private.sh
  echo "Source in Cloud Specific Vars"
popd

# Install ssh key to allow us to ssh locally
pushd ~/aos-cd/git/aos-cd-jobs/bin
  ./add_ssh_key_to_localhost.yml
  echo "Add loopback ssh"
popd

# Update cluster setup changes to the releases directory
pushd ~/aos-cd/git/aos-cd-jobs/private/files
  cp cicd_aws_cluster_setup.yml ../../../openshift-ansible-ops/playbooks/release/bin
  echo "Update cluster setup changes"
popd

# Deploy all the things
pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
  autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &
  export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
  autokeys_loader ./aws_cluster_setup.sh cicd
  # Assume we succeed for now.
  return 0
popd

# Remove ssh key to allow us to ssh locally
pushd ~/aos-cd/git/aos-cd-jobs/bin
  ./add_ssh_key_to_localhost.yml -e ssh_key_state=absent
  echo "Remove loopback ssh"
popd

echo
echo "Deployment is complete. OpenShift Console can be found at https://${MASTER_DNS_NAME}"
echo

exit 0

# vim:sw=2:ts=2:softtabstop=2:expandtab:textwidth=79
