#!/bin/bash -e

START_DIR=$(dirname "${BASH_SOURCE[0]}")
GIT_ROOT="/home/opsmedic/aos-cd/git"
TMPDIR="$HOME/aos-cd/tmp"
mkdir -p "${TMPDIR}"

VALID_ARGUMENTS=(cicd_docker_version cicd_openshift_ansible_build cicd_openshift_version)

# TMPTMP is a directory specific to each invocation. It will be
# deleted when the script terminates.
TMPTMP=$(mktemp -d -p "${TMPDIR}")

# Kills a process and all its children
killtree() {
    local parent=$1 child
    for child in $(ps -o ppid= -o pid= | awk "\$1==$parent {print \$2}"); do
        killtree $child
    done
    if kill $parent ; then
        echo "Killed background task: $parent"
    fi
}

function on_exit() {
    rm -rf "${TMPTMP}"
    # Kill anny jobs spawned by this process and any children those jobs create.
    JOBS="$(jobs -p)"
    if [[ ! -z "$JOBS" ]]; then
        for pid in $JOBS; do
            killtree $pid
        done
    fi
}

trap on_exit EXIT

function parse_and_set_vars() {
  var=$(echo $1 | awk -F= '{print $1}')

  # Check to see if arg is valid
  # Note: This is ugly.
  if [[ ! " ${VALID_ARGUMENTS[*]} " == *" ${var} "* ]]; then
    echo "The arg: \"${var}\" is invalid.  Exiting..."
    exit 1
  fi

  echo "Setting cicd-control environment variable: $1" >&2
  export $1

  # if the value is a blank string, let's unset it. not worth it!
  key=$(echo $1 | awk -F= '{print $1}')
  if [ "${key}" == "" ]; then
    unset ${key}
  fi
}

function print_usage() {
  echo
  echo "Usage: $(basename $0) -c CLUSTERNAME -o OPERATION"
  echo
  echo "  -h               display this help and exit"
  echo "  -c CLUSTERNAME   specify the CLUSTERNAME to perform the upgrade on"
  echo "  -o OPERATION     specify the upgrade OPERATION to perform"
  echo "  -e ARG           specify the extra ARG; this is the form key=value"
  echo "  -d DEPLOYMENT    specify the cluster deployment type: dedicated|online  Default: online"
  echo
  echo "Examples:"
  echo
  echo "    $(basename $0) -c prod-cluster -o upgrade < -e argument >"
  echo

}

# Let's cd into where the script is.
cd $START_DIR

# Let's unset CLUSTERNAME and OPERATION
#  to be sure it's not set elsewhere

unset CLUSTERNAME
unset OPERATION
unset DEPLOYMENT

while getopts hc:i:o:e:d: opt; do
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
        e)
            parse_and_set_vars $OPTARG
            ;;
        d)
            export DEPLOYMENT=$OPTARG
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

if [ -d "${DEPLOYMENT+x}" ]; then
  export DEPLOYMENT=online
fi

echo "Running $(basename $0) on:" >&2
echo "CLUSTER: ${CLUSTERNAME}" >&2
echo "OPERATION: ${OPERATION}" >&2
echo "DEPLOYMENT: ${DEPLOYMENT}" >&2
echo >&2

function is_running(){
  # Output to prevent ssh timeouts. Appears to timeout
  # After about an hour of inactivity.
  while true; do
    echo >&2
    echo ".... cicd-control still running: $(date) ...." >&2
    sleep 600
  done
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

function get_latest_openshift_ansible()  {
  AOS_TMPDIR="${TMPTMP}/openshift-ansible_extract"
  mkdir -p "${AOS_TMPDIR}"

  pushd "$GIT_ROOT/openshift-ansible-ops/playbooks/adhoc/get_openshift_ansible_rpms"
    /usr/bin/ansible-playbook extract_openshift_ansible_rpms.yml -e cli_type=online -e cli_release=${1} -e cli_download_dir=${AOS_TMPDIR}
  popd

  export OPENSHIFT_ANSIBLE_INSTALL_DIR="${AOS_TMPDIR}"
}

function get_master_name() {
# Outputs the name of one a master for a cluster

  # Find an appropriate master
  MASTER="$(ossh --list | grep ${CLUSTERNAME}-master | head -n 1 | cut -d " " -f 1)"

  if [[ "${MASTER}" != "${CLUSTERNAME}"-* ]]; then
      echo "Unable to find master for the specified cluster"
      exit 1
  fi

  echo "${MASTER}"
}

################################################
# CLUSTER PRE CHECK
################################################
function pre-check() {

  # Set some cluster vars
  setup_cluster_vars

  # Get the version of RPMS that will be used
  AOS_TMPDIR="${TMPTMP}/openshift-ansible_extract"
  mkdir -p "${AOS_TMPDIR}"

  # get the latest openshift-ansible rpms
  pushd "$GIT_ROOT/openshift-ansible-ops/playbooks/adhoc/get_openshift_ansible_rpms" > /dev/null
    /usr/bin/ansible-playbook get_openshift_ansible_rpms.yml -e cli_type=online -e cli_release=${oo_environment} -e cli_download_dir=${AOS_TMPDIR} &> /dev/null
  popd > /dev/null
  OS_RPM_VERSION=$(rpm -qp --queryformat "%{VERSION}\n" ${AOS_TMPDIR}/rpms/*rpm | sort | uniq )


  MASTER="$(get_master_name)"
  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/bin/yum clean all" > /dev/null
  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/sbin/atomic-openshift-excluder unexclude" > /dev/null
  OPENSHIFT_VERSION=$(/usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/bin/repoquery --quiet --pkgnarrow=repos --queryformat='%{version}-%{release}' atomic-openshift")
  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/sbin/atomic-openshift-excluder exclude" > /dev/null

  echo
  echo Openshift Ansible RPM Version: ${OS_RPM_VERSION}
  echo Openshift RPM Version: ${OPENSHIFT_VERSION}
  echo

  /usr/bin/rm -rf ${AOS_TMPDIR}
  exit 0
}

################################################
# CLUSTER LOG GATHERING
################################################
function gather_logs() {
  ./gather-logs.sh ${CLUSTERNAME}
  exit 0
}

function build_ci_msg() {
  MASTER="$(get_master_name)"
  # Streams the python script to the cluster master. Script outputs a json document.
  # Grep is to eliminate ossh verbose output -- grabbing only the key value pairs.
  /usr/local/bin/autokeys_loader ossh -l root "${MASTER}" -c "/usr/bin/python - ${CLUSTERNAME}" < build-ci-msg.py | grep '.\+=.\+'
  exit 0
}

################################################
# OPERATION: STATUS
################################################
# Stdout from 'status' invocation is sent out verbatim after an
# online-first install/upgrade. Similar to logs operation, don't
# output any stdout before this point.
function cluster_status() {
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

  # 'exec' will exit this script and turn controll over to the script being called
  exec /usr/local/bin/autokeys_loader ./aos-cd-cluster-smoke-test.sh ${CLUSTERNAME}
}

function setup_cluster_vars() {

  oo_environment="$(/usr/bin/ohi -c ${CLUSTERNAME} --get-cluster-var oo_environment)"
  if [ "$?" -ne 0 ]; then
    echo "There was a problem setting the environment for the cluster.  Exiting..."
    exit 1
  fi

}

################################################
# OPERATION: INSTALL
################################################
function install_cluster() {
#OPERATION = install
  is_running &

  set +x  # Mask sensitive data
  source "$GIT_ROOT/openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_vars.sh"
  #set -x

  CLUSTER_SETUP_TEMPLATE_FILE="$GIT_ROOT/openshift-ansible-private/private_roles/aos-cicd/files/${CLUSTERNAME}/${CLUSTERNAME}_aws_cluster_setup.yml"

  if [ ! -f ${CLUSTER_SETUP_TEMPLATE_FILE} ]; then
    echo "Unable to find ${CLUSTERNAME}'s cluster setup template file. Exiting..."
    exit 10
  fi

  # Update cluster setup changes to the releases directory
  /usr/bin/cp ${CLUSTER_SETUP_TEMPLATE_FILE} "$GIT_ROOT/openshift-ansible-ops/playbooks/release/bin"

  oo_environment="$(grep -Po '(?<=^g_environment: ).*' "${CLUSTER_SETUP_TEMPLATE_FILE}")"

  #setup_cluster_vars

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
function delete_cluster() {
  # another layer of protection for delete clusters
  if [[ "${CLUSTERNAME}" != "free-int" ]] && [[ "${CLUSTERNAME}" != "cicd" ]]; then
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
# OPERATION: GENERAL OPERATIONS CLUSTER
################################################
function cluster_operation() {

  if [ -z "${1+x}" ]; then
    echo "No CLUSTER OPERATION was specified.  Exiting..."
    exit 1
  fi

  CLUSTER_OPERATION=$1

  echo "Doing upgrade operation: ${CLUSTER_OPERATION}"

  # setup cluster vars
  setup_cluster_vars

  # Do long running operations
  is_running &

  # For online deployments, skip statuspage, get the lastest openshift-ansible
  if [ "${DEPLOYMENT}" == "online" ]; then
    # For now, let's skip statuspage operations
    export SKIP_STATUS_PAGE="true"

    # Get the latest openshift-ansible rpms
    LATEST_ANSIBLE_OPERATIONS=(install upgrade upgrade-control-plane upgrade-nodes upgrade-metrics upgrade-logging)

    if [[ " ${LATEST_ANSIBLE_OPERATIONS[*]} " == *" ${CLUSTER_OPERATION} "* ]]; then
      get_latest_openshift_ansible ${oo_environment}
    fi
  fi

  # Run the operation
  pushd ~/aos-cd/git/openshift-ansible-ops/playbooks/release/bin
    /usr/local/bin/autokeys_loader ./cicd_operations.sh -c ${CLUSTERNAME} -o ${CLUSTER_OPERATION}
  popd
}

################################################
# OPERATION: PERFORMANCE TEST1
################################################
function perf1() {
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

# Allow for "test-key" to do some testing.
# Let's get test-key stuff out of the way first
if [ "${CLUSTERNAME}" == "test-key" ]; then
  get_latest_openshift_ansible "int"
  echo "OPENSHIFT_ANSIBLE_INSTALL_DIR = [${OPENSHIFT_ANSIBLE_INSTALL_DIR}]"
  echo "Operation requested on mock cluster '${CLUSTERNAME}'. The operation is: '${OPERATION}' with options: ${ARGS}"
  echo "  OPENSHIFT_ANSIBLE_VERSION=${OPENSHIFT_ANSIBLE_VERSION}"

  exit 0
fi


case "$OPERATION" in
  install)
    update_ops_git_repos
    install_cluster
    ;;

  delete)
    update_ops_git_repos
    delete_cluster
    ;;

  legacy-upgrade)
    update_ops_git_repos
    legacy_upgrade_cluster
    ;;

  status)
    cluster_status
    ;;

  smoketest)
    smoketest
    ;;

  pre-check)
    update_ops_git_repos
    pre-check
    ;;

  build-ci-msg)
    build_ci_msg
    ;;

  perf1)
    perf1
    ;;

  *)
    update_ops_git_repos
    cluster_operation ${OPERATION}
   ;;

esac
