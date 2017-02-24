#!/bin/bash -e

function print_usage() {
  echo
  echo "Usage: $(basename $0) <clusterid> <operation> [options]"
  echo "Examples:"
  echo
  echo "    $(basename $0) testcluster install"
  echo "    $(basename $0) testcluster delete"
  echo "    $(basename $0) testcluster upgrade"
  echo
}

if [ "$#" -lt 2 ]
then
  print_usage
  exit 1
fi

# Let's cd into where the script is.
# Remember, we have to path everything based off of the script's dir
cd "$(dirname "$0")"

export CLUSTERNAME=$1
export OPERATION=$2
shift 2
ARGS="$@"

opts=`getopt -o ha: --long help,openshift-ansible: -n 'cicd-control' -- "$@"`
eval set -- "$opts"
OPENSHIFT_ANSIBLE_VERSION="latest"
help=0

while true; do
  case "$1" in
    -h | --help )    help=1; shift ;;
    -a | --openshift-ansible ) OPENSHIFT_ANSIBLE_VERSION="$2"; shift; shift ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

if [[ "$help" == "1" ]]; then
    print_usage
    exit 0
fi

# Set the version for the upgrade
export VERSION=3.5
export VERSION_UNDERSCORE=$(echo ${VERSION} | /usr/bin/tr . _)

# Allow for "test-key" to do some testing.
# For now, all we will do is echo out the $CLUSTERNAME and $OPERATION variables
# and then exit successfully.
if  [ "${CLUSTERNAME}" == "test-key" ]; then
  echo "Operation requested on mock cluster '${CLUSTERNAME}'. The operation is: '${OPERATION}' with options: ${ARGS}" 
  echo "  VERSION=${VERSION}"
  echo "  OPENSHIFT_ANSIBLE_VERSION=${OPENSHIFT_ANSIBLE_VERSION}"
  exit 0
fi

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

  source ../../openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_vars.sh

  CLUSTER_SETUP_TEMPLATE_FILE=../../openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_aws_cluster_setup.yml
  if [ ! -f ${CLUSTER_SETUP_TEMPLATE_FILE} ]; then
    echo "Unable to find ${CLUSTERNAME}'s cluster setup template file. Exiting..."
    exit 10
  fi
  
  # Update cluster setup changes to the releases directory
  echo "Update cluster setup changes..."
  /usr/bin/cp ${CLUSTER_SETUP_TEMPLATE_FILE} ../../openshift-ansible-ops/playbooks/release/bin
  
  # Deploy all the things
  pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
    /usr/local/bin/autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &> /dev/null &
    CHILDREN="$CHILDREN $!"
    echo "Will terminate $CHILDREN at the end of this script"
    export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
    export SKIP_GIT_VALIDATION=TRUE
    /usr/local/bin/autokeys_loader ./aws_cluster_setup.sh ${CLUSTERNAME}
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
    /usr/local/bin/autokeys_loader /usr/bin/ansible-playbook aws_remove_cluster.yml -e cli_clusterid=${CLUSTERNAME} -e cluster_to_delete=${CLUSTERNAME} -e run_in_automated_mode=True
  popd

  # This updates the OPs inventory
  echo "Updating the OPs inventory..."
  /usr/share/ansible/inventory/multi_inventory.py --refresh-cache --cluster=${CLUSTERNAME} >/dev/null

################################################
# UPGRADE CLUSTER
################################################
elif [ "${OPERATION}" == "upgrade" ]; then 
  echo Doing upgrade
  /usr/local/bin/autokeys_loader /usr/bin/ansible-playbook -i ./ops-to-productization-inventory.py ../../openshift-tools/openshift/installer/atomic-openshift-${VERSION}/playbooks/byo/openshift-cluster/upgrades/v${VERSION_UNDERSCORE}/upgrade.yml

else
  echo "Error. Unrecognized operation '${OPERATION}'. Exiting..."
  exit 10
fi
