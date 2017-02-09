#!/bin/bash -e

function print_usage() {
  echo
  echo "Usage: $(basename $0) <clusterid> <operation>"
  echo "Examples:"
  echo
  echo "    $(basename $0) testcluster install"
  echo "    $(basename $0) testcluster delete"
  echo "    $(basename $0) testcluster upgrade"
  echo
}

if [ "$#" -ne 2 ]
then
  print_usage
  exit 1
fi

cd "$(dirname "$0")"

CLUSTERNAME=$1
OPERATION=$2

# for now let's make sure we are using cicd
if  [ "${CLUSTERNAME}" != "cicd" ]; then
  echo "CLUSTERNAME is not 'cicd'!  Exiting..."

  exit 10
fi

source ../../openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_vars.sh

# Do we need this?
if [ $? -ne 0 ]; then
  echo "Unable to source ${CLUSTERNAME}'s variable file. Exiting..."

  exit 10
fi

CLUSTER_SETUP_TEMPLATE_FILE=../../openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_aws_cluster_setup.yml

if [ ! -f ${CLUSTER_SETUP_TEMPLATE_FILE} ]; then
  echo "Unable to find ${CLUSTERNAME}'s cluster setup template file. Exiting..."

  exit 10
fi

# update aos-cd-jobs repo


# update git repos
# This needs review. 
# This isn't very portable. This requires that the git dirs are already 
# in place to do updates
/usr/bin/ansible-playbook ./clone_ops_git_repos.yml

################################################
# CREATE CLUSTER
################################################
if [ "${OPERATION}" == "install" ]; then 
  set -o xtrace

  CHILDREN=""

  # Kill all background jobs on normal exit or signal
  trap 'kill $(jobs -p)' EXIT

  # Update cluster setup changes to the releases directory
  echo "Update cluster setup changes..."
  cp ${CLUSTER_SETUP_TEMPLATE_FILE} ../../openshift-ansible-ops/playbooks/release/bin

  # Deploy all the things
  pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
    autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &
    CHILDREN="$CHILDREN $!"
    echo "Will terminate $CHILDREN at the end of this script"
    export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
    autokeys_loader ./aws_cluster_setup.sh ${CLUSTERNAME}
  popd

  echo
  echo "Deployment is complete. OpenShift Console can be found at https://${MASTER_DNS_NAME}"
  echo

################################################
# DELETE CLUSTER
################################################
elif [ "${OPERATION}" == "delete" ]; then 

  # This updates the OPs inventory
  echo "Updating the OPs inventory..."
  /usr/share/ansible/inventory/multi_inventory.py --refresh-cache --cluster=${CLUSTERNAME} >/dev/null
  echo

  pushd ../../openshift-ansible-ops/playbooks/release/decommission
    autokeys_loader /usr/bin/ansible-playbook aws_remove_cluster.yml -e cli_clusterid=${CLUSTERNAME} -e cluster_to_delete=${CLUSTERNAME} -e run_in_automated_mode=True
  popd

  # This updates the OPs inventory
  echo "Updating the OPs inventory..."
  /usr/share/ansible/inventory/multi_inventory.py --refresh-cache --cluster=${CLUSTERNAME} >/dev/null

################################################
# UPGRADE CLUSTER
################################################
elif [ "${OPERATION}" == "upgrade" ]; then 

  echo Doing upgrade

else
  echo Error. Unrecognized operation. Exiting...
fi
