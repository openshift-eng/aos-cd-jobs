#!/bin/bash -e

START_DIR=$(dirname "$0")
GIT_ROOT="/home/opsmedic/aos-cd/git"
TMPDIR="$HOME/aos-cd/tmp"
mkdir -p "${TMPDIR}"

# TMPTMP is a directory specific to each invocation. It will be
# deleted when the script terminates.
TMPTMP=$(mktemp -d -p "${TMPDIR}")

function on_exit() {
    rm -rf "${TMPTMP}"

    # JOBS is primarily designed to kill the autokey_loader process if it was launched
    JOBS="$(jobs -p)"
    if [[ ! -z "$JOBS" ]]; then
        if kill $JOBS; then
            echo "Background tasks terminated"
        else
            echo "Unable to terminate background tasks"
        fi
    fi
}

trap on_exit EXIT

function print_usage() {
  echo
  echo "Usage: $(basename $0) -c CLUSTERNAME -o OPERATION"
  echo
  echo "  -h               display this help and exit"
  echo "  -c CLUSTERNAME   specify the CLUSTERNAME to perform the upgrade on"
  echo "  -o OPERATION     specify the upgrade OPERATION to perform"
  echo
  echo "Examples:"
  echo
  echo "    $(basename $0) -i $(basename $0) -c prod-cluster -o upgrade"
  echo
  echo "  Log Gathering Operations:"
  echo "  Output will be a tarball of cluster logs. Do not pipe to stdout."
  echo "    $(basename $0) <clusterid> logs"
  echo

}

#  echo
#  echo "Usage: $(basename $0) <clusterid> <operation> [options]"
#  echo "Examples:"
#  echo
#  echo "  Cluster Operations:"
#  echo "    $(basename $0) testcluster install"
#  echo "    $(basename $0) testcluster delete"
#  echo "    $(basename $0) testcluster upgrade"
#  echo "    $(basename $0) testcluster status"
#  echo

#if [ "$#" -lt 2 ]
#then
#  print_usage
#  exit 1
#fi

# Let's cd into where the script is.
cd $START_DIR

# Let's unset CLUSTERNAME and OPERATION
#  to be sure it's not set elsewhere

unset CLUSTERNAME
unset OPERATION

while getopts hc:i:o: opt; do
    case $opt in
        h)
            print_usage
            exit 0
            ;;
        c)
            export CLUSTERNAME=$OPTARG
            ;;
        o)
            export OPERATION=$OPTARG
            ;;
        *)
            print_usage
            exit 1
            ;;
    esac
done
shift "$((OPTIND-1))"   # Discard the options and sentinel --

# Let's make sure $CLUSTERNAME and $OPERATION are set
if [ -z "${CLUSTERNAME+x}" ]; then
  echo "No cluster was specified.  Exiting..."
  print_usage
  exit 1
fi

if [ -z "${OPERATION+x}" ]; then
  echo "No operation was specified.  Exiting..."
  print_usage
  exit 1
fi

echo "CLUSTER: ${CLUSTERNAME}"
echo "OPERATION: ${OPERATION}"


#export CLUSTERNAME=$1
#export OPERATION=$2
#shift 2
#ARGS="$@"

#opts=`getopt -o ha: --long help,openshift-ansible: -n 'cicd-control' -- "$@"`
#eval set -- "$opts"
#OPENSHIFT_ANSIBLE_VERSION="latest"
#help=0
#
#while true; do
#  case "$1" in
#    -h | --help )    help=1; shift ;;
#    -a | --openshift-ansible ) OPENSHIFT_ANSIBLE_VERSION="$2"; shift; shift ;;
#    -- ) shift; break ;;
#    * ) break ;;
#  esac
#done

#if [[ "$help" == "1" ]]; then
#    print_usage
#    exit 0
#fi

function is_running(){
  # Output to prevent ssh timeouts. Appears to timeout
  # After about an hour of inactivity.
  while true; do
    echo
    echo ".... $(date) ...."
    sleep 600
  done
}

function get_latest_openshift_ansible()  {
  AOS_TMPDIR="${TMPTMP}/openshift-ansible_extract"
  mkdir -p "${AOS_TMPDIR}"

  pushd "$GIT_ROOT/openshift-ansible-ops/playbooks/adhoc/get_openshift_ansible_rpms"
    /usr/bin/ansible-playbook extract_openshift_ansible_rpms.yml -e cli_type=online -e cli_release=$1 -e cli_download_dir=${AOS_TMPDIR}
  popd

  export OPENSHIFT_ANSIBLE_INSTALL_DIR="${AOS_TMPDIR}"
}

function get_master_name() {
# Outputs the name of one a master for a cluster

  if [ "${CLUSTERNAME}" == "test-key" ]; then
      echo "test-key-master-mock"
      return 0
  fi

  # Find an appropriate master
  MASTER="$(ossh --list | grep ${CLUSTERNAME}-master | head -n 1 | cut -d " " -f 1)"

  if [[ "${MASTER}" != "${CLUSTERNAME}"-* ]]; then
      echo "Unable to find master for the specified cluster"
      exit 1
  fi

  echo "${MASTER}"
}

function gather_logs() {
################################################
# CLUSTER LOG GATHERING
# PLEASE DO NOT ADD STDOUT OPERATIONS BEFORE HERE
################################################
# Gather the logs for the specified cluster
# OPERATION=logs
  ./gather-logs.sh ${CLUSTERNAME}
  exit 0
}

function build_ci_msg() {
#if OPERATION = build-ci-msg
  MASTER="$(get_master_name)"

  if [ "${CLUSTERNAME}" == "test-key" ]; then
      python - "${CLUSTERNAME}" < build-ci-msg.py
      exit 0
  fi

  # Streams the python script to the cluster master. Script outputs a json document.
  # Grep is to eliminate ossh verbose output -- grabbing only the json doc.
  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/bin/python - ${CLUSTERNAME}" < build-ci-msg.py | grep '^{.*'
  exit 0
}

################################################
# OPERATION: STATUS
################################################
# Stdout from 'status' invocation is sent out verbatim after an
# online-first install/upgrade. Similar to logs operation, don't
# output any stdout before this point.
function cluster_status() {
#OPERATION = status

  if [ "${CLUSTERNAME}" == "test-key" ]; then
    echo "This output represents the current status of the test-key cluster"
    echo "This is the second line"
    echo "This is the third and final"
    exit 0
  fi

  /usr/local/bin/autokeys_loader ./aos-cd-cluster-status.sh ${CLUSTERNAME}
  exit 0
}

################################################
# OPERATION: SMOKETEST
################################################
function smoketest() {
#OPERATION = smoketest
  echo "Performing smoketest on cluster: ${CLUSTERNAME}..."
  echo

  if [ "${CLUSTERNAME}" == "test-key" ]; then
    echo "This output represents the current smoketest of the test-key cluster"
    exit 0
  fi

  # 'exec' will exit this script and turn controll over to the script being called
  exec /usr/local/bin/autokeys_loader ./aos-cd-cluster-smoke-test.sh ${CLUSTERNAME}
}


function update_ops_git_repos () {
# TODO: This requires that the git dirs are already in place to do updates
# Prevent output from this operation unless it actually fails; just to keep logs cleaner
  set +e
  cd $START_DIR
  CLONE_RESULT=$(/usr/local/bin/autokeys_loader /usr/bin/ansible-playbook ./clone_ops_git_repos.yml)
  if [ "$?" != "0" ]; then
    echo "Error updating git repos"
    echo "$CLONE_RESULTS"
    exit 1
  fi
  set -e
}

function do_test_key_stuff() {
# Allow for "test-key" to do some testing.
# For now, all we will do is echo out the $CLUSTERNAME and $OPERATION variables
# and then exit successfully.
#if  [ "${CLUSTERNAME}" == "test-key" ]; then
  get_latest_openshift_ansible "int"
  echo "OPENSHIFT_ANSIBLE_INSTALL_DIR = [${OPENSHIFT_ANSIBLE_INSTALL_DIR}]"
  echo "Operation requested on mock cluster '${CLUSTERNAME}'. The operation is: '${OPERATION}' with options: ${ARGS}"
  echo "  OPENSHIFT_ANSIBLE_VERSION=${OPENSHIFT_ANSIBLE_VERSION}"

  exit 0
}

function setup_cluster_vars() {
  set +x  # Mask sensitive data
  source "$GIT_ROOT/openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_vars.sh"
  set -x

  CLUSTER_SETUP_TEMPLATE_FILE="$GIT_ROOT/openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_aws_cluster_setup.yml"

  if [ ! -f ${CLUSTER_SETUP_TEMPLATE_FILE} ]; then
    echo "Unable to find ${CLUSTERNAME}'s cluster setup template file. Exiting..."
    exit 10
  fi

  # Update cluster setup changes to the releases directory
  echo "Update cluster setup changes..."
  /usr/bin/cp ${CLUSTER_SETUP_TEMPLATE_FILE} "$GIT_ROOT/openshift-ansible-ops/playbooks/release/bin"

  # Get the version and env from the template file
  oo_version="$(grep -Po '(?<=^g_install_version: ).*' "${CLUSTER_SETUP_TEMPLATE_FILE}" | /usr/bin/cut -c 1-3)"
  oo_environment="$(grep -Po '(?<=^g_environment: ).*' "${CLUSTER_SETUP_TEMPLATE_FILE}")"
}

################################################
# OPERATION: INSTALL
################################################
function install_cluster() {
#OPERATION = install
  is_running &
  setup_cluster_vars
  get_latest_openshift_ansible ${oo_environment}

  # Deploy all the things
  pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
    /usr/local/bin/autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &> /dev/null &
    export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
    export SKIP_GIT_VALIDATION=TRUE
    /usr/local/bin/autokeys_loader ./aws_cluster_setup.sh ${CLUSTERNAME}
  popd

  echo
  echo "Deployment is complete. OpenShift Console can be found at https://${MASTER_DNS_NAME}"
  echo
}

################################################
# OPERATION: DELETE CLUSTER
################################################
function install_cluster() {
#OPERATION = delete

  # another layer of protection for delete clusters
  if [[ "${CLUSTERNAME}" != "dev-preview-int" ]] && [[ "${CLUSTERNAME}" != "cicd" ]]; then
    echo "INVALID CLUSTER, NOT DELTETING CLUSTER: '${CLUSTERNAME}'. Exiting...."
    exit 10
  fi

  # This updates the OPs inventory
  /usr/share/ansible/inventory/multi_inventory.py --refresh-cache --cluster=${CLUSTERNAME} >/dev/null
  echo "Updating the OPs inventory..."
  echo

  pushd "$GIT_ROOT/openshift-ansible-ops/playbooks/release/decommission"
    /usr/local/bin/autokeys_loader /usr/bin/ansible-playbook aws_remove_cluster.yml -e cli_clusterid=${CLUSTERNAME} -e cluster_to_delete=${CLUSTERNAME} -e run_in_automated_mode=True
  popd

  # This updates the OPs inventory
  echo "Updating the OPs inventory..."
  /usr/share/ansible/inventory/multi_inventory.py --refresh-cache --cluster=${CLUSTERNAME} >/dev/null
}

################################################
# OPERATION: UPGRADE CLUSTER
################################################
function install_cluster() {
#OPERATION = "upgrade"
  echo Doing upgrade
  is_running &
  setup_cluster_vars


  ./disable-docker-timer-hack.sh "${CLUSTERNAME}" > /dev/null &

  # Get the latest openshift-ansible rpms
  get_latest_openshift_ansible ${oo_environment}

  # Run the upgrade, including post_byo steps and config loop
  pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
    /usr/local/bin/autokeys_loader ./refresh_aws_tmp_credentials.py --refresh &> /dev/null &

    # Kill all background jobs on normal exit or signal

    export AWS_DEFAULT_PROFILE=$AWS_ACCOUNT_NAME
    export SKIP_GIT_VALIDATION=TRUE
    /usr/local/bin/autokeys_loader ./aws_online_cluster_upgrade.sh ./ops-to-productization-inventory.py ${CLUSTERNAME}
  popd
}

################################################
# OPERATION: PERFORMANCE TEST1
################################################
function perf1() {
#OPERATION = "perf1"
  if [[ "${CLUSTERNAME}" == "test-key" ]]; then
      echo "Mock run for: ${CLUSTERNAME}"
      exit 0
  fi

  if [[ "${CLUSTERNAME}" != "free-int" && "${CLUSTERNAME}" != "dev-preview-int" ]]; then
      echo "Cannot run performance test on cluster: ${CLUSTERNAME}"
      exit 1
  fi

  is_running &
  echo "Running performance test 1"
  MASTER="$(get_master_name)"

  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "sh" <<EOF
yum install -y python-ceph python-boto3 python-flask
rm -rf perf1
mkdir -p perf1
cd perf1
git clone -b svt-cicd https://github.com/openshift/svt
cd svt/openshift_performance/ci/scripts
./conc_builds_cicd.sh
EOF
}

case "$OPERATION" in
  enable-statuspage)
    enable-statuspage
    ;;

  disable-statuspage)
    disable-statuspage
    ;;

  enable-zabbix-maint)
    enable-zabbix-maint
    ;;

  disable-zabbix-maint)
    disable-zabbix-maint
    ;;

  disable-config-loop)
    disable-config-loop
    ;;

  enable-config-loop)
    enable-config-loop
    ;;

  update-yum-extra-repos)
    update-yum-extra-repos
    ;;

  update-inventory)
    update-inventory
    ;;

  upgrade)
    upgrade
    ;;

  upgrade-control-plane)
    upgrade-control-plane
    ;;

  upgrade-nodes)
    upgrade-nodes
    ;;

  generate-byo-inventory)
    generate-byo-inventory
    ;;

  upgrade-logging)
    upgrade-logging
    ;;

  upgrade-metrics)
    upgrade-metrics
    ;;

  commit-config-loop)
    commit-config-loop
    ;;

  run-config-loop)
    run-config-loop
    ;;

  *)
   enable-statuspage
   #enable-zabbix-maint
   disable-config-loop
   update-inventory
   update-yum-extra-repos
   upgrade
   upgrade-logging
   upgrade-metrics
   #commit-config-loop
   enable-config-loop
   #run-config-loop
   #disable-zabbix-maint
   disable-statuspage

esac

