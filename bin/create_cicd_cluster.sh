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

export AWS_CREDENTIALS_FILE=/home/opsmedic/.aws/credentials
export IDP_HOST=login.ops.openshift.com
export AWS_ACCOUNT_ID=639866565627
export AWS_ACCOUNT_NAME=opstest
#export USER=autokeys

# Install ssh key to allow us to ssh locally
./add_ssh_key_to_localhost.yml

cp cicd_aws_cluster_setup.yml ../git/openshift-ansible-ops/playbooks/release/bin

pushd ../git/openshift-ansible-ops/playbooks/release/bin
  autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &
  export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
  autokeys_loader ./aws_cluster_setup.sh cicd
popd

# Remove ssh key to allow us to ssh locally
./add_ssh_key_to_localhost.yml -e ssh_key_state=absent
