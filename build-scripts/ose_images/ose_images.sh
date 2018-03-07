#!/bin/bash
#
# This is a script initially designed for making images rebuilds semi-automated.
#  It has grown beyond that, but that is still the heart of the program.
#
# Required packages:
#   rhpkg
#   krb5-workstation
#   git
#
# Many options need your kerberos log in:
#   kinit
#
## COMMON VARIABLES ##
#source ose.conf

PS4='${LINENO}: '
set -o xtrace

## LOCAL VARIABLES ##
MASTER_RELEASE="3.10"    # Update version_trim_list when this changes
MAJOR_RELEASE="${MASTER_RELEASE}"  # This is a default if --branch is not specified
MINOR_RELEASE=$(echo ${MAJOR_RELEASE} | cut -d'.' -f2)

RELEASE_MAJOR=$(echo "$MAJOR_RELEASE" | cut -d . -f 1)
RELEASE_MINOR=$(echo "$MAJOR_RELEASE" | cut -d . -f 2)

DIST_GIT_BRANCH="rhaos-${MAJOR_RELEASE}-rhel-7"
#DIST_GIT_BRANCH="rhaos-3.2-rhel-7-candidate"
#DIST_GIT_BRANCH="rhaos-3.1-rhel-7"
SCRATCH_OPTION=""
BUILD_REPO="https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-building.repo"
COMMIT_MESSAGE=""
PULL_REGISTRY=brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888
PUSH_REGISTRY=registry.reg-aws.openshift.com:443
ERRATA_ID="24510"
ERRATA_PRODUCT_VERSION="RHEL-7-OSE-${MAJOR_RELEASE}"
SCRIPT_HOME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

trap "exit 1" TERM
export TOP_PID=$$

# Hard exit is designed to terminate the script even in cases
# where a function is being used like $(func).
hard_exit() {
    kill -s TERM "$TOP_PID"
}

usage() {
  echo "Usage `basename $0` [action] <options>" >&2
  echo >&2
  echo "Actions:" >&2
  echo "  build build_container :: Build containers in OSBS" >&2
  echo "  push push_images :: Push images to qe-registry" >&2
  echo "  scan_images      :: Scan images with openscap" >&2
  echo "  compare_git      :: Compare dist-git Dockerfile and other files with those in git" >&2
  echo "  compare_auto     :: Auto compare dist-git files with those in git. Sends Dockerfile diff in email" >&2
  echo "  compare_nodocker :: Compare dist-git files with those in git.  Show but do not change Dockerfile changes" >&2
  echo "  update_docker    :: Update dist-git Dockerfile version, release, or rhel" >&2
  echo "  update_compare   :: Run update_docker, compare_update, then update_docker again" >&2
  echo "  make_yaml        :: Print out yaml from Dockerfile for release" >&2
  echo "  merge_to_newest  :: Merge dist-git Release-1 to Release [--branch is required]" >&2
  #echo "  update_errata    :: Update image errata with Docker images" >&2
  #echo "  list             :: Display full list of packages / images" >&2
  echo "  test             :: Display what packages would be worked on" >&2
  echo >&2
  echo "Options:" >&2
  echo "  -h, --help          :: Show this options menu" >&2
  echo "  -v, --verbose       :: Be verbose" >&2
  echo "  -f, --force         :: Force: always do dist-git commits " >&2
  echo "  -i, --ignore        :: Ignore: do not do dist-git commits " >&2
  echo "  -d, --deps          :: Dependents: Also do the dependents" >&2
  echo "  --nochannel         :: Do not tag or push as channel latest (v3.3), or regular latest" >&2
  echo "  --nolatest          :: Do not tag or push as latest, still do channel latest" >&2
  echo "  --noversiononly     :: Do not tag or push without a release (v3.3.0.4)" >&2
  echo "  --message [message] :: Git commit message" >&2
  echo "  --group [group]     :: Which group list to use (base metrics logging jenkins misc all base_only)" >&2
  echo "  --package [package] :: Which package to use e.g. openshift-enterprise-pod-docker" >&2
  echo "  --version [version] :: Change Dockerfile version e.g. 3.1.1.2" >&2
  echo "  --release [version] :: Change Dockerfile release e.g. 3" >&2
  echo "  --bump_release      :: Change Dockerfile release by 1 e.g. 3->4" >&2
  echo "  --rhel [version]    :: Change Dockerfile RHEL version e.g. rhel7.2:7.2-35 or rhel7:latest" >&2
  echo "  --branch [version]  :: Use a certain dist-git branch  default[${DIST_GIT_BRANCH}]" >&2
  echo "  --repo [Repo URL]   :: Use a certain yum repo  default[${BUILD_REPO}]" >&2
#  echo "  --errata_id [id]      :: errata id to use  default[${ERRATA_ID}]" >&2
#  echo "  --errata_pv [version] :: errata product version to use  default[${ERRATA_PRODUCT_VERSION}]" >&2
  echo "  --pull_reg [registry] :: docker registry to pull from  default[${PULL_REGISTRY}]" >&2
  echo "  --push_reg [registry] :: docker registry to push to  default[${PUSH_REGISTRY}]" >&2
  echo "  --prebuilt [package]  :: Package has already been prebuilt correctly" >&2
  echo "  --user [username]     :: Username for rhpkg" >&2
  echo >&2
  echo "Note: --group and --package can be used multiple times" >&2
  popd &>/dev/null
  exit 1
}

add_to_list() {
  if ! [[ ${packagelist} =~ "::${1}::" ]] ; then
    export packagelist+=" ::${1}::"
    if [ "${VERBOSE}" == "TRUE" ] ; then
      echo "----------"
      echo ${packagelist}
    fi
  fi
}

add_group_to_list() {
  case ${1} in
    base)
      add_to_list openshift-enterprise-base-docker
      if [ ${MAJOR_RELEASE} == "3.1" ] || [ ${MAJOR_RELEASE} == "3.2" ] ; then
        add_to_list openshift-enterprise-openvswitch-docker
        add_to_list openshift-enterprise-pod-docker
        add_to_list openshift-enterprise-docker
        add_to_list openshift-enterprise-haproxy-router-base-docker
        add_to_list openshift-enterprise-dockerregistry-docker
        add_to_list openshift-enterprise-keepalived-ipfailover-docker
        add_to_list openshift-enterprise-recycler-docker
        add_to_list aos-f5-router-docker
        add_to_list openshift-enterprise-deployer-docker
        add_to_list openshift-enterprise-node-docker
        add_to_list openshift-enterprise-sti-builder-docker
        add_to_list openshift-enterprise-docker-builder-docker
        add_to_list openshift-enterprise-haproxy-router-docker
      else
        add_to_list openshift-enterprise-pod-docker
        # Removed for OIT testing
        # add_to_list aos3-installation-docker
        add_to_list openshift-enterprise-docker

          # dockerregistry moving to its own github repo in 3.8
          if [[ "${RELEASE_MAJOR}" == 3 && "${RELEASE_MINOR}" -lt 8 ]]; then
                add_to_list openshift-enterprise-dockerregistry-docker
          fi

        add_to_list openshift-enterprise-egress-router-docker
        add_to_list openshift-enterprise-keepalived-ipfailover-docker
        add_to_list aos-f5-router-docker
        add_to_list openshift-enterprise-deployer-docker
        add_to_list openshift-enterprise-haproxy-router-docker
        add_to_list openshift-enterprise-node-docker
        add_to_list openshift-enterprise-recycler-docker
        add_to_list openshift-enterprise-sti-builder-docker
        add_to_list openshift-enterprise-docker-builder-docker
	if [ ${MAJOR_RELEASE} == "3.4" ]; then
	 	# This is no longer required after moving to ansible
        	add_to_list logging-deployment-docker
	        add_to_list metrics-deployer-docker
	fi
        add_to_list logging-curator-docker
        if [ ${MAJOR_RELEASE} != "3.3" ] && [ ${MAJOR_RELEASE} != "3.4" ]  && [ ${MAJOR_RELEASE} != "3.5" ] ; then
          add_to_list logging-auth-proxy-docker
          add_to_list logging-elasticsearch-docker
          add_to_list logging-fluentd-docker
          add_to_list logging-kibana-docker
          add_to_list metrics-cassandra-docker
          add_to_list metrics-hawkular-metrics-docker
          add_to_list metrics-hawkular-openshift-agent-docker
          add_to_list metrics-heapster-docker
          add_group_to_list "jenkins"
          add_to_list registry-console-docker
          #add_group_to_list "asb"
          add_to_list openshift-enterprise-service-catalog-docker
          add_to_list openshift-enterprise-federation-docker
          add_to_list openshift-enterprise-cluster-capacity-docker
          add_to_list container-engine-docker
          add_to_list ose-egress-http-proxy-docker
        fi
        if [ ${MAJOR_RELEASE} == "3.7" ] || [ ${MAJOR_RELEASE} == "3.8" ] || [ ${MAJOR_RELEASE} == "3.9" ]; then
          add_to_list golang-github-prometheus-prometheus-docker
          add_to_list golang-github-prometheus-alertmanager-docker
          add_to_list golang-github-openshift-prometheus-alert-buffer-docker
	      add_to_list golang-github-openshift-oauth-proxy-docker
	      add_to_list logging-eventrouter-docker
	    fi
        add_to_list openshift-enterprise-openvswitch-docker
      fi
    ;;
    misc)
      add_to_list image-inspector-docker
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] ; then
        add_to_list registry-console-docker
      fi
    ;;
    installer)
      echo "aos3-installation-docker not available"
      # Disabled for OIT testing
      # add_to_list aos3-installation-docker
    ;;
    #asb)  # Should move to oit management
    #      add_to_list openshift-enterprise-mediawiki-docker
    #      add_to_list openshift-enterprise-apb-base-docker
    #      add_to_list openshift-enterprise-asb-docker
    #      add_to_list openshift-enterprise-mediawiki
    #      add_to_list openshift-enterprise-postgresql
    #;;
    rhel-extras)
      add_to_list etcd-docker
      add_to_list etcd3-docker
    ;;
    logging)
      add_to_list logging-auth-proxy-docker
      if [ ${MAJOR_RELEASE} == "3.1" ] || [ ${MAJOR_RELEASE} == "3.2" ] ; then
        add_to_list logging-deployment-docker
      else
        add_to_list logging-curator-docker
      fi
      add_to_list logging-elasticsearch-docker
      add_to_list logging-fluentd-docker
      add_to_list logging-kibana-docker
    ;;
    jenkins | jenkins-all )
      if [[ "${RELEASE_MAJOR}" == 3 && "${RELEASE_MINOR}" -lt 7 ]]; then
        add_to_list openshift-jenkins-docker
      fi
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] && [ ${MAJOR_RELEASE} != "3.3" ] ; then
        add_to_list openshift-jenkins-2-docker
      fi
      add_group_to_list "jenkins-slaves"
    ;;
    jenkins-plain )
      add_to_list openshift-jenkins-docker
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] && [ ${MAJOR_RELEASE} != "3.3" ] ; then
        add_to_list openshift-jenkins-2-docker
      fi
    ;;
    jenkins-slaves )
      # if [ ${MAJOR_RELEASE} != "3.7" ] ; then
      if false; then  # temporary for initial testing. In case it needs to come back.
        add_to_list jenkins-slave-base-rhel7-docker
        add_to_list jenkins-slave-maven-rhel7-docker
        add_to_list jenkins-slave-nodejs-rhel7-docker
      fi
    ;;
    metrics)
      add_to_list metrics-cassandra-docker
      add_to_list metrics-hawkular-metrics-docker
      if [ ${MAJOR_RELEASE} == "3.1" ] || [ ${MAJOR_RELEASE} == "3.2" ] ; then
        add_to_list metrics-deployer-docker
      fi
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] && [ ${MAJOR_RELEASE} != "3.3" ] && [ ${MAJOR_RELEASE} != "3.4" ] ; then
        add_to_list metrics-hawkular-openshift-agent-docker
      fi
      add_to_list metrics-heapster-docker
    ;;
    deployer)
      add_to_list logging-deployment-docker
      add_to_list metrics-deployer-docker
    ;;
    base_only)
      add_to_list openshift-enterprise-base-docker
      if [ ${MAJOR_RELEASE} == "3.1" ] || [ ${MAJOR_RELEASE} == "3.2" ] ; then
        add_to_list openshift-enterprise-openvswitch-docker
        add_to_list openshift-enterprise-pod-docker
        add_to_list openshift-enterprise-docker
        add_to_list openshift-enterprise-haproxy-router-base-docker
        add_to_list openshift-enterprise-dockerregistry-docker
        add_to_list openshift-enterprise-keepalived-ipfailover-docker
        add_to_list openshift-enterprise-recycler-docker
        add_to_list aos-f5-router-docker
        add_to_list openshift-enterprise-deployer-docker
        add_to_list openshift-enterprise-node-docker
        add_to_list openshift-enterprise-sti-builder-docker
        add_to_list openshift-enterprise-docker-builder-docker
        add_to_list openshift-enterprise-haproxy-router-docker
      else
        add_to_list openshift-enterprise-pod-docker
        # Removed for OIT testing
        # add_to_list aos3-installation-docker
        add_to_list openshift-enterprise-docker
        add_to_list openshift-enterprise-dockerregistry-docker
        add_to_list openshift-enterprise-egress-router-docker
        add_to_list openshift-enterprise-keepalived-ipfailover-docker
        add_to_list aos-f5-router-docker
        add_to_list openshift-enterprise-deployer-docker
        add_to_list openshift-enterprise-haproxy-router-docker
        add_to_list openshift-enterprise-node-docker
        add_to_list openshift-enterprise-recycler-docker
        add_to_list openshift-enterprise-sti-builder-docker
        add_to_list openshift-enterprise-docker-builder-docker
        add_to_list logging-deployment-docker
        add_to_list metrics-deployer-docker
        add_to_list openshift-enterprise-openvswitch-docker
      fi
    ;;
    oso)
      add_to_list oso-accountant-docker
      add_to_list oso-notifications-docker
      # add_to_list oso-reconciler-docker    ## Deprecated per vdinh
      # add_to_list oso-user-analytics-docker  ## Deprecated per vdinh
    ;;
    efs)
      add_to_list efs-provisioner-docker
    ;;
    egress)
      add_to_list openshift-enterprise-egress-router-docker
      add_to_list ose-egress-http-proxy-docker
    ;;
  esac
}

setup_dist_git() {
  if ! klist &>${workingdir}/logs/${container}.output ; then
    echo "Error: Kerberos token not found." ; popd &>${workingdir}/logs/${container}.output ; exit 1
  fi
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_dist_git **"
    echo " container:  ${container} branch: ${branch} "
  fi

  # Determine if this is an apbs/ Docker repo (e.g. "apbs/openshift-enterprise-mediawiki")
  # Anything other than "rpms" requires the type specified in the clone command.
  export ctype_prefix="${dict_image_type[${container}]}"
  if [ "$ctype_prefix" != "" ]; then
    ctype_prefix="$ctype_prefix/"
  fi

  rhpkg ${USER_USERNAME} clone "${ctype_prefix}${container}" &>${workingdir}/logs/${container}.output
  if [ "$?" != "0" ]; then
    sleep 60
    rhpkg ${USER_USERNAME} clone "${ctype_prefix}${container}" &>${workingdir}/logs/${container}.output
      if [ "$?" != "0" ]; then
        sleep 60
        rhpkg ${USER_USERNAME} clone "${ctype_prefix}${container}" &>${workingdir}/logs/${container}.output
      fi
  fi
  if [ -d ${container} ] ; then
    pushd ${container} >${workingdir}/logs/${container}.output
    rhpkg switch-branch "${branch}" &>${workingdir}/logs/${container}.output
    popd >${workingdir}/logs/${container}.output
  else
    echo " Failed to clone container: ${container}"
  fi
}

setup_dockerfile() {
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_dockerfile **"
    echo " container:  ${container} branch: ${branch} "
  fi
  mkdir -p "${container}" &>/dev/null
  pushd ${container} >/dev/null
  export ctype="${dict_image_type[${container}]}"
  if [ "$ctype" == "" ]; then
    ctype="rpms"
  fi

  wget -q -O Dockerfile http://dist-git.host.prod.eng.bos.redhat.com/cgit/${ctype}/${container}/plain/Dockerfile?h=${branch}
  if [ "$?" != "0" ]; then
    wget -q -O Dockerfile http://pkgs.devel.redhat.com/cgit/${ctype}/${container}/plain/Dockerfile?h=${branch}
    if [ "$?" != "0" ]; then
        wget -q -O Dockerfile http://pkgs.devel.redhat.com/cgit/${ctype}/${container}.git/plain/Dockerfile?h=${branch}
        if [ "$?" != "0" ]; then
            echo "Unable to download Dockerfile"
            exit 1
        fi
    fi
  fi
  popd >/dev/null
}

setup_git_repo() {

  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_git_repo **"
    echo " git_repo: ${git_repo} "
    echo " git_path: ${git_path} "
  fi

  set -e # enable hard error fail, we do not want this to go ahead if *anything* goes wrong
  # repo may be entered as github.com/reponame#branch
  # so we can secify the branch manually
  # cut out the base repo URL and the branch name, if exists
  git_base_url=$(echo "${git_repo}#" | cut -d "#" -f 1)
  branch_override=$(echo "${git_repo}#" | cut -d "#" -f 2)
  pushd "${workingdir}" >/dev/null

  # get the name of the repo so we can cd into that directory for branch checkout
  repo_name=$(echo "${git_path}/" | cut -d "/" -f 1)

  # Clone the repo if it has not been cloned already
  if [ ! -d "${repo_name}" ]; then
    git clone -q ${git_base_url}
  fi

  cd "${repo_name}"
  # if there was a branch named in the git_repo, use it
  if [ ! -z "${branch_override}" ] ; then
    git checkout "${branch_override}"
  else
    # Otherwise, switch to master. Don't assume we are there already, since this
    # repo can be used multiple times with multiple branches.
    git checkout "master"
  fi
  # we are in the repo dir git_path is relative to the workingdir, so move up one dir
  cd ..

  pushd "${git_path}" >/dev/null
  set +e # back to ignoring errors

  # If we are running in online:stg mode, we want to update dist-git with
  # content from the stage branch, not from master.
  if [ "${git_branch}" == "master" -a "${BUILD_MODE}" == "online:stg" ]; then
    # See if this repo has a stage branch
    git checkout "stage"
    if [ "$?" == "0" ]; then
        echo "Running in stage branch of: ${git_repo}"
    fi
  fi

  popd >/dev/null
  popd >/dev/null

}

check_builds() {
  pushd "${workingdir}/logs" >/dev/null

  # For each buildlog in the working logs directory
  ls -1 *buildlog | while read line
  do
    package=`echo ${line} | cut -d'.' -f1`

    ### Example .buildlog ###
    # Created task: 13461148
    # Task info: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=13461148
    # Watching tasks (this may be safely interrupted)...
    # 13461148 buildContainer (noarch): free
    # 13461148 buildContainer (noarch): free -> open (x86-036.build.eng.bos.redhat.com)

    taskid=`cat ${line} | grep -i "Created task:" | head -n 1 | awk '{print $3}'`
    echo "Brew task URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${taskid}"

    ### Example taskinfo output ###
    # Task: 13464674
    # Type: buildContainer
    # Owner: ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com
    # State: closed
    # Created: Mon Jun 19 04:38:21 2017
    # Started: Mon Jun 19 04:38:23 2017
    # Finished: Mon Jun 19 05:28:49 2017
    # Host: x86-036.build.eng.bos.redhat.com
    # Log Files:
    #   /mnt/redhat/brewroot/work/tasks/4674/13464674/checkout-for-labels.log
    #   /mnt/redhat/brewroot/work/tasks/4674/13464674/openshift-incremental.log

    n=0
    until [ $n -ge 5 ]
    do
        state=$(brew taskinfo "${taskid}" | grep -i '^State:') && break
        echo "Brew task URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${taskid}"
        n=$[$n+1]
        sleep 60
    done

    state=$(echo "$state" | awk '{print $2}')

    if [ "$n" == "5" ]; then
        echo "Unable to acquire brew task state"
        state="internal-timeout"
    fi

    if [ "$state" == "open" -o "$state" == "free" ]; then # free state means brew is waiting for a free builder
        echo "brew build for $package is still running..."
    else
      if [ "$state" == "closed" ]; then
          echo "==== ${package} IMAGE COMPLETED ===="
          echo "::${package}::" >> ${workingdir}/logs/finished
          echo "::${package}::" >> ${workingdir}/logs/success
          sed -i "/::${package}::/d" ${workingdir}/logs/working
      else
          # Examples of other states: "failure", "canceled", "internal-timeout"
          echo "=== ${package} IMAGE BUILD FAILED due to state: $state ==="
          echo "::${package}::" >> ${workingdir}/logs/finished
          sed -i "/::${package}::/d" ${workingdir}/logs/working
          if grep -q -e "already exists" ${line} ; then
              grep -e "already exists" ${line} | cut -d':' -f4-
              echo "Package with same NVR has already been built"
              echo "::${package}::" >> ${workingdir}/logs/prebuilt
          else

                RF="${workingdir}/retries"
                if [ -f "$RF" ]; then
                    retries="$(cat $RF)"
                else
                    retries="10"
                fi

                retries=$(($retries - 1))
                echo -n "$retries" > $RF

              if [ "$retries" == "0" ]; then
                  echo "::${package}::" >> ${workingdir}/logs/buildfailed
                  echo "Failed logs"
                  ls -1 ${package}.*
                  cp -f ${package}.* ${workingdir}/logs/failed-logs/
              else
                    echo "Detected failed build: ${package} but there are $retries left, so triggering it again in 5 minutes."
                    echo "Failed brew URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${taskid}"
		            sleep 300
                    export container="$package"
                    F="$FORCE"
                    export FORCE="TRUE"
                    start_build_image
                    export FORCE="$F"  # Restore old value after the call

                    # Pretend the build never terminated with an error
                    continue
              fi
          fi
      fi
      mv ${line} ${package}.watchlog done/
    fi
  done

  popd >/dev/null
}

wait_for_all_builds() {

  # While there are .buildlog files in workindir/logs, builds are still running
  buildcheck=`ls -1 ${workingdir}/logs/*buildlog 2>/dev/null`
  while ! [ "${buildcheck}" == "" ]
  do
    echo "=== waiting for these builds ==="
    date
    echo "${buildcheck}"
    sleep 120
    check_builds
    buildcheck=`ls -1 ${workingdir}/logs/*buildlog 2>/dev/null`
  done

  echo "=== PREBUILT PACKAGES ==="
  cat ${workingdir}/logs/prebuilt
  echo
  echo "=== FAILED PACKAGES ==="
  cat ${workingdir}/logs/buildfailed
  echo
  buildfailed=`ls -1 ${workingdir}/logs/failed-logs/`
  if [ -n "${buildfailed}" ] ; then
    echo "=== FULL FAILED LOGS ==="
    ls -1 ${workingdir}/logs/failed-logs/ | while read line
    do
      echo "${workingdir}/logs/failed-logs/${line}"
      cat "${workingdir}/logs/failed-logs/${line}"
      echo
    done

    echo "Failed build occurred. Exiting."
    hard_exit
  fi
}

check_build_dependencies() {
  if ! grep -q ::${build_dependency}:: ${workingdir}/logs/finished && ! grep -q ::${build_dependency}:: ${workingdir}/logs/working  ; then
    echo "  ERROR: build dependency ${build_dependency} is not built, nor scheduled to be built."
    echo "         Failing ${build_dependency}"
    echo "  ERROR INFO: If you know the proper version of ${build_dependency}"
    echo "              has already been built add the following to your build command line"
    echo "                  --prebuilt ${build_dependency}"
    echo "::${build_dependency}::" >> ${workingdir}/logs/finished
    echo "::${build_dependency}::" >> ${workingdir}/logs/buildfailed
  fi
  depcheck=`grep ::${build_dependency}:: ${workingdir}/logs/finished`
  while [ "${depcheck}" == "" ]
  do
    now=`date`
    echo "Waiting for ${build_dependency} to be built - ${now}"
    sleep 120
    check_builds
    depcheck=`grep ::${build_dependency}:: ${workingdir}/logs/finished`
  done
}

build_image() {
    rhpkg ${USER_USERNAME} container-build ${SCRATCH_OPTION} --repo ${BUILD_REPO} > ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-errata-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-errata-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-signed-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-signed-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    echo -n "  Waiting for build to start ."
    sleep 10
    taskid=`cat ${workingdir}/logs/${container}.buildlog | grep -i "Created task:" | head -n 1 | awk '{print $3}'`
    while [ "${taskid}" == "" ]
    do
      echo -n "."
      sleep 10
      taskid=`cat ${workingdir}/logs/${container}.buildlog | grep -i "Created task:" | head -n 1 | awk '{print $3}'`
      if grep -q -e "Unknown build target:" -e "buildContainer (noarch) failed" -e "is not a valid repo" -e "server startup error" ${workingdir}/logs/${container}.buildlog ; then
        echo " error"
        echo "=== ${container} IMAGE BUILD FAILED ==="
        mv ${workingdir}/logs/${container}.buildlog ${workingdir}/logs/done/
        echo "::${container}::" >> ${workingdir}/logs/finished
        echo "::${container}::" >> ${workingdir}/logs/buildfailed
        sed -i "/::${container}::/d" ${workingdir}/logs/working
        echo "Failed logs"
        ls -1 ${workingdir}/logs/done/${container}.*
        cp -f ${workingdir}/logs/done/${container}.* ${workingdir}/logs/failed-logs/
        taskid="FAILED"
      fi
    done
    echo " "
    if ! [ "${taskid}" == "FAILED" ] ; then
      brew watch-logs ${taskid} >> ${workingdir}/logs/${container}.watchlog 2>&1 &
    fi
}

start_build_image() {
  pushd "${workingdir}/${container}" >/dev/null
  if [ "${FORCE}" == "TRUE" ] || [[ ${parent} =~ "::${container}::" ]] ; then
    build_image
  else
    check_build_dependencies
    failedcheck=`grep ::${build_dependency}:: ${workingdir}/logs/buildfailed`
    if [ "${failedcheck}" == "" ] ; then
      build_image
    else
      echo "  dependency error: ${build_dependency} failed to build"
      echo "=== ${container} IMAGE BUILD FAILED ==="
      echo "::${container}::" >> ${workingdir}/logs/finished
      echo "::${container}::" >> ${workingdir}/logs/buildfailed
      sed -i "/::${container}::/d" ${workingdir}/logs/working
    fi
  fi
  popd >/dev/null
}

update_dockerfile() {
  pushd "${workingdir}/${container}" >/dev/null

  find . -name ".osbs*" -prune -o -name "Dockerfile*" -type f -print | while read line
  do
    if [ "${update_version}" == "TRUE" ] ; then
      sed -i -e "s/version=\".*\"/version=\"${version_version}\"/" ${line}
      grep "FROM .*openshift3/" ${line}
      if [ "$?" == "0" ]; then   # Only upgrade versions that are not FROM rhel
        sed -i -e "s/FROM \(.*\):.*/FROM \1:${version_version}-${release_version}/" ${line}
      fi
    fi
    if [ "${update_release}" == "TRUE" ] ; then
      sed -i -e "s/release=\".*\"/release=\"${release_version}\"/" ${line}

      if [[ "${release_version}" == *"."* ]]; then  # Use newer dot notation?
        nr_start=$(echo ${release_version} | rev | cut -d "." -f2- | rev)
        # For any build using this method, we want a tag without the last field (e.g. "3.7.0-0.100.5" instead of
        # "3.7.0-0.100.5.8"). The shorter tag is what OCP will actually use when it needs to pull an image
        # associated with its current version. The last field in the release is used for refreshing images and
        # is not necessary outside of pulp.
        echo "${version_version}-${nr_start}" > additional-tags  # e.g. "v3.7.0-0.100.2" . This is the key tag OCP will use
        echo "v${MAJOR_RELEASE}" >> additional-tags  # e.g. "v3.7" . For users/images where exact matches aren't critical
        git add additional-tags
      fi

    fi
    if [ "${bump_release}" == "TRUE" ] ; then
      # Example release line: release="2"
      old_release_version=$(grep release= ${line} | cut -d'=' -f2 | cut -d'"' -f2 )
      if [[ "${old_release_version}" == *"."* ]]; then  # Use newer dot notation?
        # The new build pipline initializes the Dockerfile to have release=REL.INT.STG.0
        # If the release=X.Y.Z.B, bump the B
        nr_start=$(echo ${old_release_version} | rev | cut -d "." -f2- | rev)
        nr_end=$(echo ${old_release_version} | rev | cut -d . -f 1 | rev)
        new_release="${nr_start}.$(($nr_end+1))"

        # For any build using this method, we want a tag without the last field (e.g. "3.7.0-0.100.5" instead of
        # "3.7.0-0.100.5.8"). The shorter tag is what OCP will actually use when it needs to pull an image
        # associated with its current version. The last field in the release is used for refreshing images and
        # is not necessary outside of pulp.
        echo "v${version_version}-${nr_start}" > additional-tags  # e.g. "v3.7.0-0.100.2" . This is the key tag OCP will use
        echo "v${MAJOR_RELEASE}" >> additional-tags  # e.g. "v3.7" . For users/images where exact matches aren't critical
        git add additional-tags
      else
          let new_release_version=$old_release_version+1
      fi
      sed -i -e "s/release=\".*\"/release=\"${new_release_version}\"/" ${line}
      if [ "${VERBOSE}" == "TRUE" ] ; then
        echo "old_release_version: ${old_release_version} new_release_version: ${new_release_version} file: ${line}"
        grep release= ${line}
      fi
    fi
    if [ "${update_rhel}" == "TRUE" ] ; then
      sed -i -e "s/FROM rhel7.*/FROM ${rhel_version}/" ${line}
    fi
  done
  popd >/dev/null
}

merge_to_newest_dist_git() {
  pushd "${workingdir}/${container}" >/dev/null
  rhpkg switch-branch "${branch}" >/dev/null
  if [ -s Dockerfile ] ; then
    echo " Dockerfile already in new branch."
    echo " Assuming merge has already happened."
    echo " Skipping."
  else
    rhpkg switch-branch "rhaos-${MAJOR_RELEASE_MINUS}-rhel-7" >/dev/null
    rhpkg switch-branch "${branch}" >/dev/null
    echo " Merging ..."
    git merge -m "Merge branch rhaos-${MAJOR_RELEASE_MINUS}-rhel-7 into rhaos-${MAJOR_RELEASE}-rhel-7" rhaos-${MAJOR_RELEASE_MINUS}-rhel-7 >/dev/null
    echo " Pushing to dist-git ..."
    rhpkg push  >/dev/null 2>&1
      if [ "$?" != "0" ]; then
        sleep 60
        rhpkg push  >/dev/null 2>&1
          if [ "$?" != "0" ]; then
            sleep 60
            rhpkg push  >/dev/null 2>&1
          fi
      fi

    echo " Fixing ose yum repo"
    sed -i "s|rhel-7-server-ose-${MAJOR_RELEASE_MINUS}-rpms|rhel-7-server-ose-${MAJOR_RELEASE}-rpms|g" Dockerfile
    echo " Fixing additional-tags"
    TAG_TYPE="default"
    for current_tag in ${tag_list} ; do
      if [ "${current_tag}" == "all-v" ] ; then
        TAG_TYPE="all-v"
      fi
    done
    if [ "${TAG_TYPE}" == "default" ] ; then
      sed -i "s|v${MAJOR_RELEASE_MINUS}|v${MAJOR_RELEASE}|g" additional-tags
    else
      echo "v${MAJOR_RELEASE}" >> additional-tags
    fi
    echo " Pushing to dist-git ..."
    rhpkg commit -p -m "Update ose yum repo and/or additional-tags" >/dev/null 2>&1
  fi
  popd >/dev/null
}

overwrite_dist_git_branch(){
  pushd "${workingdir}/${container}" >/dev/null
  echo "${branch}"
  source_branch_files=$(mktemp -d)
  rhpkg switch-branch "${branch}"
  if [ "$?" -ne "0" ]; then
    echo "Unable to switch to ${branch} branch."
    exit 1
  fi

  cp -r ./ "${source_branch_files}"
  ls -al "${source_branch_files}"
  rhpkg switch-branch "${TARGET_DIST_GIT_BRANCH}"
  if [ "$?" -ne "0" ]; then
    echo "Unable to switch to ${TARGET_DIST_GIT_BRANCH} branch."
    exit 1
  fi
  #remove everything except .git
  find . -path ./.git -prune -o -exec rm -rf {} \; 2> /dev/null
  rsync -av --exclude='.git' "${source_branch_files}/" ./
  git add .
  rhpkg commit -p -m "Overwriting with contents of ${branch} branch" >/dev/null 2>&1
  popd >/dev/null
}

inject_files_to_dist_git() {
  pushd "${workingdir}/${container}" >/dev/null
  echo "${branch}"
  rhpkg switch-branch "${branch}"
  if [[ -f ${DIST_GIT_INJECT_PATH} ]]; then
    cp "${DIST_GIT_INJECT_PATH}" ./
  elif [[ -d ${DIST_GIT_INJECT_PATH} ]]; then
    cp -r "${DIST_GIT_INJECT_PATH}/*" ./
  else
    echo "${DIST_GIT_INJECT_PATH} is not a valid file or directory!"
    hard_exit
  fi
    #statements
  ls -al ./
  git add .
  rhpkg commit -p -m "Adding ${DIST_GIT_INJECT_PATH} to root of branch" >/dev/null 2>&1
  popd >/dev/null
}

show_git_diffs() {
  pushd "${workingdir}/${container}" >/dev/null
  if ! [ "${git_style}" == "dockerfile_only" ] ; then
    echo "  ---- Checking files changed, added or removed ----"
    #echo "diff --brief -r ${workingdir}/${container} ${workingdir}/${git_path} | grep -v -e ${container}/Dockerfile -e ${git_path}/Dockerfile -e ' Dockerfile' -e ${container}/additional-tags -e ' additional-tags' -e ${container}/.git -e ${git_path}/.git -e ' .git' -e ${container}/.osbs -e ' .osbs'"
    extra_check=$(diff --brief -r ${workingdir}/${container} ${workingdir}/${git_path} | grep -v -e ${container}/Dockerfile -e ${git_path}/Dockerfile -e ' Dockerfile' -e ${container}/additional-tags -e ' additional-tags' -e ${container}/.git -e ${git_path}/.git -e ' .git' -e ${container}/.osbs -e ' .osbs')
    if ! [ "${extra_check}" == "" ] ; then
      echo "${extra_check}"
    fi
    differ_check=$(echo "${extra_check}" | grep " differ")
    new_file=$(echo "${extra_check}" | grep "Only in ${workingdir}/${git_path}")
    old_file=$(echo "${extra_check}" | grep "Only in ${workingdir}/${container}")
    if ! [ "${differ_check}" == "" ] ; then
      echo "  ---- Non-Docker file changes ----"
      echo "${differ_check}" | while read differ_line
      do
        myold_file=$(echo "${differ_line}" | awk '{print $2}')
        mynew_file=$(echo "${differ_line}" | awk '{print $4}')
        if [ "${VERBOSE}" == "TRUE" ] ; then
          diff -u ${myold_file} ${mynew_file}
        fi
        cp -vf ${mynew_file} ${myold_file}
        git add ${myold_file}
      done
    fi
    if ! [ "${old_file}" == "" ] ; then
      echo "  ---- Removed Non-Docker files ----"
      #echo "${old_file}"
      working_path="${workingdir}/${container}/"
      echo "${old_file}" | while read old_file_line
      do
        myold_file=$(echo "${old_file_line}" | awk '{print $4}')
        myold_dir=$(echo "${old_file_line}" | awk '{print $3}' | cut -d':' -f1)
        myold_dir_file="${myold_dir}/${myold_file}"
        myold_dir_file_trim="${myold_dir_file#$working_path}"
        git rm -r ${myold_dir_file_trim}
      done
    fi
    if ! [ "${new_file}" == "" ] ; then
      echo "  ---- New Non-Docker files ----"
      #echo "${new_file}"
      working_path="${workingdir}/${git_path}"
      echo "${new_file}" | while read new_file_line
      do
        mynew_file=$(echo "${new_file_line}" | awk '{print $4}')
        mynew_dir=$(echo "${new_file_line}" | awk '{print $3}' | cut -d':' -f1)
        mynew_dir_file="${mynew_dir}/${mynew_file}"
        mynew_dir_file_trim="${mynew_dir_file#$working_path}"
        cp -rv ${working_path}/${mynew_dir_file_trim} ${workingdir}/${container}/${mynew_dir_file_trim}
        git add ${workingdir}/${container}/${mynew_dir_file_trim}
      done
    fi
  fi
  echo "  ---- Checking Dockerfile changes ----"
  if ! [ -f .osbs-logs/Dockerfile.git.last ] ; then
    cp ${workingdir}/${git_path}/${git_dockerfile} .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.git.last
    newdiff="First time comparing Dockerfiles, nothing to compare to."
  fi
  cp ${workingdir}/${git_path}/${git_dockerfile} .osbs-logs/Dockerfile.git.new
  diff --label Dockerfile.orig --label Dockerfile -u .osbs-logs/Dockerfile.git.last .osbs-logs/Dockerfile.git.new >> .osbs-logs/Dockerfile.patch.new
  if [ -s .osbs-logs/Dockerfile.patch.new ] ; then
    mv -f .osbs-logs/Dockerfile.patch.new .osbs-logs/Dockerfile.patch
    cp -f Dockerfile .osbs-logs/Dockerfile.dist-git.last
    patch -p0 --fuzz=3 -i .osbs-logs/Dockerfile.patch
    if [ "${?}" != "0" ] ; then
      echo "FAILED PATCH"
      echo "Exiting ..."
      hard_exit
    fi
    mv -f .osbs-logs/Dockerfile.git.new .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.patch
    git add .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.dist-git.last
    git add Dockerfile
    newdiff="$(diff -u Dockerfile .osbs-logs/Dockerfile.dist-git.last)"
  else
    rm -f .osbs-logs/Dockerfile.patch.new .osbs-logs/Dockerfile.git.new
  fi
  if ! [ "${newdiff}" == "" ] || ! [ "${extra_check}" == "" ] ; then
    echo "${newdiff}"
    echo " "
    echo "Changes occured "
    if [ "${FORCE}" == "TRUE" ] ; then
      echo "  Force Option Selected - Assuming Continue"
      rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
    else
      echo "  To view/modify changes, go to: ${workingdir}/${container}"
      echo "(c)ontinue [rhpkg commit], (i)gnore, (q)uit [exit script] : "
      read choice_raw < /dev/tty
      choice=$(echo "${choice_raw}" | awk '{print $1}')
      case "${choice}" in
        c | C | continue )
          rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
          ;;
        i | I | ignore )
          ;;
        q | Q | quit )
          break
          ;;
        * )
          echo "${choice} not and option.  Assuming ignore"
          ;;
      esac
    fi
  fi
  popd >/dev/null

}

show_git_diffs_nice_docker() {
  pushd "${workingdir}/${container}" >/dev/null
  if ! [ "${git_style}" == "dockerfile_only" ] ; then
    echo "  ---- Checking files changed, added or removed ----"
    extra_check=$(diff --brief -r ${workingdir}/${container} ${workingdir}/${git_path} | grep -v -e ${container}/Dockerfile -e ${git_path}/Dockerfile -e ' Dockerfile' -e ${container}/additional-tags -e ' additional-tags' -e ${container}/.git -e ${git_path}/.git -e ' .git' -e ${container}/.osbs -e ' .osbs')
    if ! [ "${extra_check}" == "" ] ; then
      echo "${extra_check}"
    fi
    differ_check=$(echo "${extra_check}" | grep " differ")
    new_file=$(echo "${extra_check}" | grep "Only in ${workingdir}/${git_path}")
    old_file=$(echo "${extra_check}" | grep "Only in ${workingdir}/${container}")
    if ! [ "${differ_check}" == "" ] ; then
      echo "  ---- Non-Docker file changes ----"
      echo "${differ_check}" | while read differ_line
      do
        myold_file=$(echo "${differ_line}" | awk '{print $2}')
        mynew_file=$(echo "${differ_line}" | awk '{print $4}')
        if [ "${VERBOSE}" == "TRUE" ] ; then
          diff -u ${myold_file} ${mynew_file}
        fi
        cp -vf ${mynew_file} ${myold_file}
        git add ${myold_file}
      done
    fi
    if ! [ "${old_file}" == "" ] ; then
      echo "  ---- Removed Non-Docker files ----"
      #echo "${old_file}"
      working_path="${workingdir}/${container}/"
      echo "${old_file}" | while read old_file_line
      do
        myold_file=$(echo "${old_file_line}" | awk '{print $4}')
        myold_dir=$(echo "${old_file_line}" | awk '{print $3}' | cut -d':' -f1)
        myold_dir_file="${myold_dir}/${myold_file}"
        myold_dir_file_trim="${myold_dir_file#$working_path}"
        git rm -r ${myold_dir_file_trim}
      done
    fi
    if ! [ "${new_file}" == "" ] ; then
      echo "  ---- New Non-Docker files ----"
      #echo "${new_file}"
      working_path="${workingdir}/${git_path}"
      echo "${new_file}" | while read new_file_line
      do
        mynew_file=$(echo "${new_file_line}" | awk '{print $4}')
        mynew_dir=$(echo "${new_file_line}" | awk '{print $3}' | cut -d':' -f1)
        mynew_dir_file="${mynew_dir}/${mynew_file}"
        mynew_dir_file_trim="${mynew_dir_file#$working_path}"
        cp -rv ${working_path}/${mynew_dir_file_trim} ${workingdir}/${container}/${mynew_dir_file_trim}
        git add ${workingdir}/${container}/${mynew_dir_file_trim}
      done
    fi
  fi
  echo "  ---- Checking Dockerfile changes ----"
  if ! [ -f .osbs-logs/Dockerfile.git.last ] ; then
    cp ${workingdir}/${git_path}/${git_dockerfile} .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.git.last
    newdiff="First time comparing Dockerfiles, nothing to compare to."
  fi
  cp ${workingdir}/${git_path}/${git_dockerfile} .osbs-logs/Dockerfile.git.new
  diff --label Dockerfile.orig --label Dockerfile -u .osbs-logs/Dockerfile.git.last .osbs-logs/Dockerfile.git.new >> .osbs-logs/Dockerfile.patch.new
  if [ -s .osbs-logs/Dockerfile.patch.new ] ; then
    mv -f .osbs-logs/Dockerfile.patch.new .osbs-logs/Dockerfile.patch
    cp -f Dockerfile .osbs-logs/Dockerfile.dist-git.last
    patch -p0 --fuzz=3 -i .osbs-logs/Dockerfile.patch
    if [ "${?}" != "0" ] ; then
      echo "FAILED PATCH"
      echo "Exiting ..."
      hard_exit
    fi
    mv -f .osbs-logs/Dockerfile.git.new .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.patch
    git add .osbs-logs/Dockerfile.git.last
    git add .osbs-logs/Dockerfile.dist-git.last
    git add Dockerfile
    newdiff="$(diff -u Dockerfile .osbs-logs/Dockerfile.dist-git.last)"
  else
    rm -f .osbs-logs/Dockerfile.patch.new .osbs-logs/Dockerfile.git.new
  fi
  if ! [ "${newdiff}" == "" ] || ! [ "${extra_check}" == "" ] ; then
    echo " "
    echo "Changes occured "
    echo "Committing non-Dockerfile changes "
    mv -f .osbs-logs/Dockerfile.diff.new .osbs-logs/Dockerfile.diff 2> /dev/null
    git add .osbs-logs/Dockerfile.diff 2> /dev/null
    if ! [ "${newdiff}" == "" ] ; then
      echo >> ${workingdir}/logs/mailfile
      echo "===== ${container} =====" >> ${workingdir}/logs/mailfile
      echo "${newdiff}" >> ${workingdir}/logs/mailfile
      echo "e-mailling Dockerfile changes "
      echo " "
      echo "${newdiff}"
    fi
    rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null 2>&1
  fi
  popd >/dev/null

}

show_dockerfile_diffs() {
  pushd "${workingdir}/${container}" >/dev/null
  if ! [ -d .osbs-logs ] ; then
    mkdir .osbs-logs
  fi
  if ! [ -f .osbs-logs/Dockerfile.last ] ; then
    touch .osbs-logs/Dockerfile.last
  fi
  echo "  ---- Checking Dockerfile changes ----"
  newdiff=`diff -u0 .osbs-logs/Dockerfile.last Dockerfile`
  if [ "${newdiff}" == "" ] ; then
    echo "    None "
  else
    echo "${newdiff}"
    echo " "
    if [ "${FORCE}" == "TRUE" ] ; then
      echo "  Force Option Selected - Assuming Continue"
      /bin/cp -f Dockerfile .osbs-logs/Dockerfile.last
      git add .osbs-logs/Dockerfile.last
      rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
    elif [ "${IGNORE}" == "TRUE" ] ; then
      echo "  Ignore Option Selected - Not committing"
    else
      echo "(c)ontinue [replace old diff], (i)gnore [leave old diff], (q)uit [exit script] : "
      read choice_raw < /dev/tty
      choice=$(echo "${choice_raw}" | awk '{print $1}')
      case "${choice}" in
        c | C | continue )
          /bin/cp -f Dockerfile .osbs-logs/Dockerfile.last
          git add .osbs-logs/Dockerfile.last
          rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
          ;;
        i | I | ignore )
          ;;
        q | Q | quit )
          break
          ;;
        * )
          echo "${choice} not and option.  Assuming ignore"
          ;;
      esac
    fi
  fi
  popd >/dev/null

}

show_yaml() {
  pushd "${workingdir}/${container}" >/dev/null
  package_version=`grep version= Dockerfile | cut -d'"' -f2`
  package_release=`grep release= Dockerfile | cut -d'"' -f2`
  if ! [ "${NOTLATEST}" == "TRUE" ] ; then
    YAML_LATEST=",latest"
  fi
  version_check=`echo ${package_version} | cut -c1-3`
  case ${version_check} in
    v3. )
      version_trim=`echo ${package_version} | cut -d'.' -f-2`
      YAML_CHANNEL="${version_trim},"
    ;;
    3.1 | 3.2 | 3.3 ) YAML_CHANNEL="v${version_check}," ;;
    * ) YAML_CHANNEL="v3.1,v3.2,v3.3" ;;
  esac
  for image_name in ${docker_name_list}
  do
    echo "---"
    echo "repository: ${image_name}"
    echo "tags: ${YAML_CHANNEL}${package_version},${package_version}-${package_release}${YAML_LATEST}"
    echo "build: ${container}-${package_version}-${package_release}"
    echo "repository_tag: ${image_name}:${package_version}-${package_release}"
  done
  popd >/dev/null
}

add_errata_build() {
  pushd "${workingdir}/${container}" >/dev/null
  package_version=`grep version= Dockerfile | cut -d'"' -f2`
  package_release=`grep release= Dockerfile | cut -d'"' -f2`
  echo "Adding ${container}-${package_version}-${package_release} to errata ${ERRATA_ID} ${ERRATA_PRODUCT_VERSION} ..."
  ${SCRIPT_HOME}/et_add_image ${ERRATA_ID} ${ERRATA_PRODUCT_VERSION} ${container}-${package_version}-${package_release}
  popd >/dev/null
}

function retry {
  local n=1
  local max=10
  local delay=120
  while true; do
    "$@" && break || {
      if [[ $n -lt $max ]]; then
        ((n++))
        echo "Command failed. Attempt $n/$max:"
        sleep $delay;
      else
        echo "This command failed after $n attempts: $@"
        return 1
      fi
    }
  done
}

function push_image {
    brew_image_url="$1"  # The source image we want to push with a new tag; e.g. brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/openshift3/ose-pod:v3.6.173.0.5-1
    brew_image_sha="$2"   # The imageid of the source image; e.g. sha256:714da0bca70977eb6420159665ae7325d077d9ed438f9c73a6a08f9fd8a7c092
    image_path="$3"  # e.g. "openshift3/ose"
    image_name=$(echo ${image_path}/ | cut -d / -f 2)  # e.g. "ose"
    image_tag="$4"  # The new tag

    # If the destination registry contains "/", assume it is specifying a "repo"
    # that we should push into and do not specify the repo ourselves.
    if [[ "${PUSH_REGISTRY}" == *"/"* ]]; then
        target_image_url="${PUSH_REGISTRY}/${image_name}:${image_tag}"
    else
        target_image_url="${PUSH_REGISTRY}/${image_path}:${image_tag}"
    fi

    # The push_cache directory will contain a history of pushes performed by this
    # buildvm where a file named after the full image name (including tag) is populated
    # with the imageid which was pushed to the PUSH_REGISTRY. If we are asked to push
    # an image:tag and the brew_image_id matches what is in the cache, we skip the push.
    pc_dir="$HOME/push_cache"
    mkdir -p "$pc_dir"

    # Remove unsafe chars from the push_cache filename
    pc_filename="${pc_dir}/$( echo -n "$target_image_url" | tr / _ | tr : _ )"

    cached_image_sha=$(cat "$pc_filename") # See if we have a record of pushing this image
    if [ "$cached_image_sha" == "$brew_image_sha" ]; then
        echo "SKIPPING PUSH of $target_image_url due to push cache. It appears buildvm has pushed this image recently."
        return 0
    fi

    # Now, try to avoid re-pushing images that already have already been pushed.
    # See if the image is stored on buildvm. If it is, assume it has been pushed and return immediately.
    local_image_sha=$(docker inspect --format="{{.Id}}" "${target_image_url}") # Record the target image id if we have it locally

    if [ "$local_image_sha" == "$brew_image_sha" ]; then
        echo "SKIPPING PUSH of $target_image_url . It appears buildvm has pushed this image recently."
        # Keep a cache of what we have pushed to try and speed up subsequent pushes.
        echo -n "$local_image_sha" > "$pc_filename"
        return 0
    fi

    # TODO: The above checks can be improved dramatically if we can check the imageid directly in registry.ops.
    # Unfortunately, registry.ops is presently returning schemaVerion: 1 instead of 2. Thus, we can't determine the image id.
    # When we can, query the registry directly to see if the imageid is already tagged the way we want.
    # curl  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" -X GET -vvv -k https://registry.ops.openshift.com/v2/${REPO}/manifests/${TAG}


    # If there is a mismatch, tag the image and push it.
    docker tag "${brew_image_url}" "${target_image_url}" | tee -a ${workingdir}/logs/push.image.log

    retry docker push "$target_image_url"
    if [ $? -ne 0 ]; then
        echo "OH NO!!! There was a problem pushing the image."
        echo "::BAD_PUSH ${container} ${target_image_url}::" >> ${workingdir}/logs/buildfailed
        sed -i "/::${target_image_url}::/d" ${workingdir}/logs/working
        hard_exit
    fi

    # Keep a cache of what we have pushed to try and speed up subsequent pushes.
    echo -n "$brew_image_sha" > "$pc_filename"

    echo "::${target_image_url}::" >> ${workingdir}/logs/finished
    sed -i "/::${target_image_url}::/d" ${workingdir}/logs/working

    echo | tee -a ${workingdir}/logs/push.image.log
}

start_push_image() {
  pushd "${workingdir}/${container}" >/dev/null
  image_path=$(grep " name=" Dockerfile | cut -d'"' -f2)  # e.g. "openshift3/ose-deployer"

  if ! [ "${update_version}" == "TRUE" ] ; then
    version_version=`grep version= Dockerfile | cut -d'"' -f2`
  fi

  if ! [ "${update_release}" == "TRUE" ] ; then
    release_version=`grep release= Dockerfile | cut -d'"' -f2`
    if [ -z "$release_version" ]; then
        release_version=1
    fi
  fi

  START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
  echo "====================================================" >>  ${workingdir}/logs/push.image.log
  echo "  ${container} ${image_path}:${version_version}-${release_version}" | tee -a ${workingdir}/logs/push.image.log
  echo "    START: ${START_TIME}" | tee -a ${workingdir}/logs/push.image.log
  echo | tee -a ${workingdir}/logs/push.image.log
  # Do our pull
  brew_image_url="${PULL_REGISTRY}/${image_path}:${version_version}-${release_version}"
  retry docker pull "${brew_image_url}"
  if [ $? -ne 0 ]; then
    echo "OH NO!!! There was a problem pulling the image."
    echo "::BAD_PULL ${container} ${image_path}:${version_version}-${release_version}::" >> ${workingdir}/logs/buildfailed
    sed -i "/::${container}::/d" ${workingdir}/logs/working
    hard_exit
  else
    brew_image_sha=$(docker inspect --format="{{.Id}}" "${brew_image_url}") # Record the recently pulled image id

    echo | tee -a ${workingdir}/logs/push.image.log
    # Work through what tags to push to, one group at a time
    for current_tag in ${tag_list} ; do
      case ${current_tag} in
        default )
          # Full name - <name>:<version>-<release>   (e.g. something like "v3.6.140-1" or "v3.7.0-0.100.4.0")
          push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_version}-${release_version}" | tee -a ${workingdir}/logs/push.image.log
          echo | tee -a ${workingdir}/logs/push.image.log

          # If using new dot notation, strip off last release field and push. See update_docker_file for details.
          if [[ "${release_version}" == *"."* ]]; then  # Using newer dot notation?
            nr_start=$(echo ${release_version} | rev | cut -d "." -f2- | rev)  # Strip off the last field of the release string
            # Push with last release field stripped off since it is a "bump" field we use for refreshing images.
            push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_version}-${nr_start}" | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
          fi

          # Name and Version - <name>:<version>
          push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_version}" | tee -a ${workingdir}/logs/push.image.log

          # Latest - <name>:latest
          if ! [ "${NOTLATEST}" == "TRUE" ] ; then
            push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "latest" | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
        single-v )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim="v${MAJOR_RELEASE}"    # ex. "v3.6"
            push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_trim}" | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
        all-v )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim_list="v3.1 v3.2 v3.3 v3.4 v3.5 v3.6 v3.7 v3.8 v3.9"
            for version_trim in ${version_trim_list} ; do
              echo "  TAG/PUSH: ${PUSH_REGISTRY}/${image_path}:${version_trim}" | tee -a ${workingdir}/logs/push.image.log
              docker tag ${PULL_REGISTRY}/${image_path}:${version_version}-${release_version} ${PUSH_REGISTRY}/${image_path}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
              echo | tee -a ${workingdir}/logs/push.image.log
              push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_trim}" | tee -a ${workingdir}/logs/push.image.log
              echo | tee -a ${workingdir}/logs/push.image.log
            done
          fi
        ;;
        three-only )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim=`echo ${version_version} | sed 's|v||g' | cut -d'.' -f-3`
            push_image "${brew_image_url}" "${brew_image_sha}" "${image_path}" "${version_trim}" | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
      esac
    done
    if ! [ "${alt_image_path}" == "" ] ; then   # alt_image_path should be something like openshift3/test-thing
        push_image "${brew_image_url}" "${brew_image_sha}" "${alt_image_path}" "${version_version}" | tee -a ${workingdir}/logs/push.image.log
        if ! [ "${NOTLATEST}" == "TRUE" ] ; then
            push_image "${brew_image_url}" "${brew_image_sha}" "${alt_image_path}" "latest" | tee -a ${workingdir}/logs/push.image.log
        fi
    fi
  fi

  STOP_TIME=$(date +"%Y-%m-%d %H:%M:%S")
  echo | tee -a ${workingdir}/logs/push.image.log
  echo "FINISHED: ${container} START TIME: ${START_TIME}  STOP TIME: ${STOP_TIME}" | tee -a ${workingdir}/logs/push.image.log
  echo | tee -a ${workingdir}/logs/push.image.log
  popd >/dev/null
}

get_image_url() {
  dockerfile=$1
  name=$(grep " name=" "${dockerfile}" | cut -d'"' -f2)
  version=$(grep version= "${dockerfile}" | cut -d'"' -f2)
  release=$(grep release= "${dockerfile}" | cut -d'"' -f2)
  echo "${PULL_REGISTRY}/${name}:${version}-${release}"
}

check_dependents() {
  if ! [ "${dependent_list_new}" == "" ] ; then
    dependent_list_working="${dependent_list_new}"
    dependent_list_new=""
    for line in "${dependent_list_working}"
    do
      if [ "${VERBOSE}" == "TRUE" ] ; then
        echo "Checking dependents for: ${line}"
      fi

      for index in ${!dict_image_from[@]}; do
        if [[ ${dependent_list} =~ "::${index}::" ]] ; then
          if [ "${VERBOSE}" == "TRUE" ] ; then
            echo "  Already have on list: ${index}"
          fi
        else
          checkdep=$(echo "${dict_image_from[${index}]}" | awk '{print $2}')
          if [ "${VERBOSE}" == "TRUE" ] ; then
            echo "  Not on list - checking: ${index}"
            echo "    Dependency is: ${checkdep}"
          fi
          if [[ ${dependent_list} =~ "::${checkdep}::" ]] ; then
            export dependent_list+="::${index}:: "
            export dependent_list_new+="::${index}:: "
            add_to_list ${index}
            if [ "${VERBOSE}" == "TRUE" ] ; then
              echo "      Added to build list: ${index}"
            fi
          fi
        fi
      done
    done
    check_dependents
  fi
}

build_container() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  start_build_image
  popd >/dev/null
}

git_compare() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  setup_git_repo
  show_git_diffs
  popd >/dev/null
}

compare_nice_docker() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  setup_git_repo
  show_git_diffs_nice_docker
  popd >/dev/null
}

docker_update() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  update_dockerfile
  show_dockerfile_diffs
  popd >/dev/null
}

build_yaml() {
  pushd "${workingdir}" >/dev/null
  setup_dockerfile
  show_yaml
  popd >/dev/null
}

merge_to_newest() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  merge_to_newest_dist_git
  popd >/dev/null
}

update_errata() {
  pushd "${workingdir}" >/dev/null
  setup_dockerfile
  add_errata_build
  popd >/dev/null
}

push_images() {
  pushd "${workingdir}" >/dev/null
  setup_dockerfile
  start_push_image
  popd >/dev/null
}

dist_git_copy() {
  pushd "${workingdir}" >/dev/null
  echo "Source Branch: ${branch}"
  echo "Target Branch: ${TARGET_DIST_GIT_BRANCH}"
  echo "Doing dist_git_copy: ${container}"
  if [ -z "${TARGET_DIST_GIT_BRANCH}" ]; then
      echo "Must provide --source_branch for dist_git_copy"
      hard_exit
  fi
  setup_dist_git
  overwrite_dist_git_branch
  popd >/dev/null
}

dist_git_branch_check() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  pushd "${workingdir}/${container}" >/dev/null
  rhpkg switch-branch "${branch}"
  if [ "$?" -ne "0" ]; then
    echo "${container}" >> "${workingdir}/missing_branch.log"
  fi
  popd >/dev/null
  popd >/dev/null
}

dist_git_migrate() {
  pushd "${workingdir}" >/dev/null
  setup_dist_git
  pushd "${workingdir}/${container}" >/dev/null
  from_branch=$(echo "${branch}" | cut -d "-" -f2)
  to_branch=$(echo "${TARGET_DIST_GIT_BRANCH}" | cut -d "-" -f2)
  rhpkg switch-branch "${TARGET_DIST_GIT_BRANCH}"
  if [ "$?" -ne "0" ]; then
    echo "${container} has no ${TARGET_DIST_GIT_BRANCH} branch!"
    exit 1
  fi

  # update repo enable
  echo "Updating repo enable entries..."
  sed -i -e "s/yum-config-manager\s*--enable\s*rhel-7-server-ose-${from_branch}-rpms/yum-config-manager --enable rhel-7-server-ose-${to_branch}-rpms/g" ./Dockerfile
  cat ./Dockerfile
  git diff --exit-code
  if [ "$?" -ne "0" ]; then
    echo "Changes have been made. Commiting back to dist-git."
    rhpkg commit -p -m "Migrating from ${branch} to ${TARGET_DIST_GIT_BRANCH}"
  fi

  popd >/dev/null
  popd >/dev/null
}

dist_git_inject() {
  pushd "${workingdir}" >/dev/null
  echo "Path to inject: ${DIST_GIT_INJECT_PATH}"
  echo "Target Branch: ${branch}"
  echo "Doing dist_git_inject: ${container}"
  if [ -z "${DIST_GIT_INJECT_PATH}" ]; then
      echo "Must provide --source_branch for dist_git_copy"
      hard_exit
  fi
  setup_dist_git
  inject_files_to_dist_git
  popd >/dev/null
}

test_function() {
  echo -e "container: ${container}\tdocker names: ${dict_image_name[${container}]}"
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo -e "dependency: ${build_dependency}\tbranch: ${branch}"
  fi
}

if [ "$#" -lt 1 ] ; then
  usage
fi

# Get our arguments
while [[ "$#" -ge 1 ]]
do
key="$1"
case $key in
    compare_git | git_compare | compare_nodocker | compare_auto | merge_to_newest | update_docker | docker_update | build_container | build | make_yaml | push_images | push | update_compare | update_errata | test | dist_git_copy | dist_git_inject | dist_git_branch_check | dist_git_migrate | scan_images)
      export action="${key}"
      ;;
    list)
      export action="${key}"
      export group_list="${group_list} all"
      ;;
    --group)
      export group_list="${group_list} $2"
      shift
      ;;
    --package)
      export parent+=" ::$2::"
      add_to_list "$2"
      shift
      ;;
    --version)
      version_version="$2"
      export update_version="TRUE"
      shift
      ;;
    --release)
      release_version="$2"
      export update_release="TRUE"
      shift
      ;;
    --bump_release)
      export really_bump_release="TRUE"
      export bump_release="TRUE"
      ;;
    --rhel)
      rhel_version="$2"
      export update_rhel="TRUE"
      shift
      ;;
    --branch)
      DIST_GIT_BRANCH="$2"
      export MAJOR_RELEASE=`echo ${DIST_GIT_BRANCH}| cut -d'-' -f2`
      export MINOR_RELEASE=$(echo ${MAJOR_RELEASE} | cut -d'.' -f2)
      export RELEASE_MAJOR=$(echo "$MAJOR_RELEASE" | cut -d . -f 1)
      export RELEASE_MINOR=$(echo "$MAJOR_RELEASE" | cut -d . -f 2)
      shift
      ;;
    --target_branch)
      TARGET_DIST_GIT_BRANCH="$2"
      shift
      ;;
    --inject_path)
      DIST_GIT_INJECT_PATH="$2"
      shift
      ;;
    --repo)
      BUILD_REPO="$2"
      shift
      ;;
    --errata_id)
      ERRATA_ID="$2"
      shift
      ;;
    --errata_pv)
      ERRATA_PRODUCT_VERSION="$2"
      shift
      ;;
    --pull_reg)
      PULL_REGISTRY="$2"
      shift
      ;;
    --push_reg)
      PUSH_REGISTRY="$2"
      shift
    ;;
    --message)
      COMMIT_MESSAGE="$2"
      shift
    ;;
    --user)
      USERNAME="$2"
      USER_USERNAME="--user $2"
      shift
    ;;
    --prebuilt)
      export prebuilt_list="${prebuilt_list} $2"
      shift
    ;;
    -d|--dep|--deps|--dependents)
      export DEPENDENTS="TRUE"
      ;;
    --nochannel | --notchannel)
      export NOCHANNEL="TRUE"
      export NOTLATEST="TRUE"
      ;;
    --nolatest | --notlatest)
      export NOTLATEST="TRUE"
      ;;
    --noversiononly )
      export NOVERSIONONLY="TRUE"
      ;;
    -v|--verbose)
      export VERBOSE="TRUE"
      ;;
    -f|--force)
      export FORCE="TRUE"
      export REALLYFORCE="TRUE"
      ;;
    -i|--ignore)
      export IGNORE="TRUE"
      ;;
    --scratch)
      export SCRATCH_OPTION=" --scratch "
      ;;
    -h|--help)
      usage  # unknown option
      ;;
    *)
      echo "Unknown Option: ${key}"
      usage  # unknown option
      exit 4
      ;;
esac
shift # past argument or value
done

# Setup variables
if [ -f ${SCRIPT_HOME}/ose.conf ] ; then
  source ${SCRIPT_HOME}/ose.conf
elif [ -f /etc/ose.conf ] ; then
  source /etc/ose.conf
else
  echo "Unable to find ose.conf"
  echo "Expecting it to be ${SCRIPT_HOME}/ose.conf or /etc/ose.conf"
  echo "Exiting ..."
  exit 42
fi

if [ "$?" != "0" ]; then
    echo "Error parsing ose.conf"
    exit 1
fi

# Setup groups
for group_input in ${group_list}
do
  if [ "${group_input}" == "all" ] ; then
    add_group_to_list base
    add_group_to_list logging
    add_group_to_list metrics
    if [ ${MAJOR_RELEASE} == "${MASTER_RELEASE}" ] ; then
      add_group_to_list jenkins
      add_to_list image-inspector-docker
    fi
    if [ "${MAJOR_RELEASE}" != "3.1" ] && [ "${MAJOR_RELEASE}" != "3.2" ] ; then
      add_to_list registry-console-docker
    fi
  else
    add_group_to_list "${group_input}"
  fi
done

# Setup Merge to Newest
if [ "${action}" == "merge_to_newest" ] ; then
  MINOR_RELEASE=$(echo ${MAJOR_RELEASE} | cut -d'.' -f2)
  let MINOR_RELEASE_MINUS=${MINOR_RELEASE}-1
  MAJOR_RELEASE_MINUS="$(echo ${MAJOR_RELEASE} | cut -d'.' -f1).${MINOR_RELEASE_MINUS}"
  if ! [ "${FORCE}" == "TRUE" ] ; then
    echo
    echo "We will be merging rhaos-${MAJOR_RELEASE_MINUS}-rhel-7 into rhaos-${MAJOR_RELEASE}-rhel-7"
    echo "Is this correct (N/y)"
    read choice
    case "${choice}" in
      y | Y | yes | Yes )
        echo
        echo "Starting merging ..."
      ;;
      *)
        echo
        echo "y/Y/yes/Yes was not chosen, exiting"
        echo "  You can use --force to skip this question"
        exit 5
      ;;
    esac
  fi
fi


# Setup directory
if ! [ "${action}" == "test" ] && ! [ "${action}" == "list" ] ; then
  workingdir=$(mktemp -d /var/tmp/ose_images-XXXXXX)
  pushd "${workingdir}" &>/dev/null
  mkdir -p logs/done
  mkdir -p logs/failed-logs
  echo "::None::" >> logs/finished
  echo "1" >> logs/try
  touch logs/buildfailed logs/working logs/prebuilt logs/success logs/mailfile
  echo "Using working directory: ${workingdir}"
fi

# Setup prebuilts
for prebuilt_package in ${prebuilt_list}
do
  echo "::${prebuilt_package}::" >> logs/finished
  echo "::${prebuilt_package}::" >> logs/prebuilt
done

# Setup dependents
if [ "${DEPENDENTS}" == "TRUE" ] ; then
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "Dependents Parent: ${parent}"
  fi
  for item_name in ${packagelist}
  do
    container_name=$(echo "${item_name}" | cut -d':' -f3)
    if [ "${VERBOSE}" == "TRUE" ] ; then
      echo "Item Name: ${item_name}"
      echo "Container: ${container_name}"
    fi
    if ! [ "${container_name}" == "" ] ; then
      export dependent_list+="::${container_name}:: "
      export dependent_list_new+="::${container_name}:: "
    fi
  done
  check_dependents
else
  export parent=""
fi


# Openshift ansible CI triggers off a change to to the openshift3/ose image in registry.ops
# to perform its testing. When it triggers, it expects there to be a "latest" puddle with
# the exact version of OCP within the image available.
# Directly after image pushing, we create this latest puddle. However, to minimize the time
# between the image landing the the puddle being created, make sure ose is the *last*
# image we push.
if [ "$action" == "push_images" -o "$action" == "push" ]; then
    if [[ "${packagelist}" == *"::openshift-enterprise-docker::"* ]]; then
        # Remove ::openshift-enterprise-docker:: from the list and add it to the end
        export packagelist="${packagelist//::openshift-enterprise-docker::} ::openshift-enterprise-docker::"
    fi
fi


# Function to do the work for each item in the list
do_work_each_package() {
for unique_package in ${packagelist}
do
  [ -z "${unique_package}" ] && continue
  export branch="${DIST_GIT_BRANCH}"
  export container=$(echo "${unique_package}" | cut -d':' -f3)
  export build_dependency=$(echo "${dict_image_from[${container}]}" | awk '{print $2}')
  case "$action" in
    build_container | build )
      echo "=== ${container} ==="
      echo "::${container}::" >> ${workingdir}/logs/working
      build_container
    ;;
    compare_git | git_compare )
      export git_repo=$(echo "${dict_git_compare[${container}]}" | awk '{print $1}')
      export git_path=$(echo "${dict_git_compare[${container}]}" | awk '{print $2}')
      export git_dockerfile=$(echo "${dict_git_compare[${container}]}" | awk '{print $3}')
      export git_style=$(echo "${dict_git_compare[${container}]}" | awk '{print $4}')
      if [ "${COMMIT_MESSAGE}" == "" ] ; then
        COMMIT_MESSAGE="Sync origin git to ose dist-git "
      fi
      echo "=== ${container} ==="
      if ! [ "${git_repo}" == "None" ] ; then
        git_compare
      else
        echo " No git repo to compare to."
        echo " Skipping"
      fi
    ;;
    compare_nodocker | compare_auto )
      export git_repo=$(echo "${dict_git_compare[${container}]}" | awk '{print $1}')
      export git_path=$(echo "${dict_git_compare[${container}]}" | awk '{print $2}')
      export git_dockerfile=$(echo "${dict_git_compare[${container}]}" | awk '{print $3}')
      export git_style=$(echo "${dict_git_compare[${container}]}" | awk '{print $4}')
      if [ "${COMMIT_MESSAGE}" == "" ] ; then
        COMMIT_MESSAGE="Sync origin git to ose dist-git "
      fi
      echo "=== ${container} ==="
      if ! [ "${git_repo}" == "None" ] ; then
        compare_nice_docker
      else
        echo " No git repo to compare to."
        echo " Skipping"
      fi
    ;;
    update_docker | docker_update )
      if [ "${COMMIT_MESSAGE}" == "" ] ; then
        COMMIT_MESSAGE="Updating Dockerfile version and release"
      fi
      echo "=== ${container} ==="
      docker_update
    ;;
    update_compare )
      if [ "${REALLYFORCE}" == "TRUE" ] ; then
        export FORCE="TRUE"
      fi
      if [ "${really_bump_release}" == "TRUE" ] ; then
        export bump_release="TRUE"
      fi
      export git_repo=$(echo "${dict_git_compare[${container}]}" | awk '{print $1}')
      export git_path=$(echo "${dict_git_compare[${container}]}" | awk '{print $2}')
      export git_dockerfile=$(echo "${dict_git_compare[${container}]}" | awk '{print $3}')
      export git_style=$(echo "${dict_git_compare[${container}]}" | awk '{print $4}')
      echo "=== ${container} ==="
      if [ "${COMMIT_MESSAGE}" == "" ] ; then
        COMMIT_MESSAGE="Updating Dockerfile version and release"
      fi
      export FORCE="TRUE"
      docker_update
      if ! [ "${git_repo}" == "None" ] ; then
        if [ "${COMMIT_MESSAGE}" == "" ] ; then
          COMMIT_MESSAGE="Sync origin git to ose dist-git "
        fi
        if [ "${REALLYFORCE}" == "TRUE" ] ; then
          export FORCE="TRUE"
        else
          export FORCE="FALSE"
        fi
        git_compare
        if [ "${COMMIT_MESSAGE}" == "" ] ; then
          COMMIT_MESSAGE="Reupdate Dockerfile after compare"
        fi
        export FORCE="TRUE"
        export bump_release="FALSE"
        docker_update
      else
        echo " No git repo to compare to."
        echo " Skipping"
      fi
    ;;
    make_yaml )
      docker_name_list="${dict_image_name[${container}]}"
      if ! [ "${docker_name_list}" == "" ] ; then
        build_yaml
      fi
    ;;
    merge_to_newest )
      echo "=== ${container} ==="
      export tag_list="${dict_image_tags[${container}]}"
      merge_to_newest
    ;;
    update_errata )
      if ! [ -f ${SCRIPT_HOME}/et_add_image ] ; then
        echo "./et_add_image required"
        exit 3
      fi
      docker_name_list="${dict_image_name[${container}]}"
      if ! [ "${docker_name_list}" == "" ] ; then
        update_errata
      else
        echo "Skipping ${container} - Image for building only"
      fi
    ;;
    push_images | push )
      echo "=== ${container} ==="
      export brew_name=$(echo "${dict_image_name[${container}]}" | awk '{print $1}')
      export alt_image_path=$(echo "${dict_image_name[${container}]}" | awk '{print $2}')
      export tag_list="${dict_image_tags[${container}]}"
      if ! [ "${brew_name}" == "" ] ; then
        echo "::${container}::" >> ${workingdir}/logs/working
        push_images
      else
        echo "  Skipping ${container} - Image for building only"
      fi
    ;;
    scan_images )
      set -e
      echo "=== ${container} ==="
      if [ ! "${dict_image_name[${container}]}" ] ; then
        echo "  Skipping ${container} - Image for building only"
        continue
      fi
      setup_dockerfile
      image=$(get_image_url "${workingdir}/${container}/Dockerfile")
      if ! retry docker pull "${image}"; then
        echo >&2 "OH NO!!! There was a problem pulling the image."
        hard_exit
      fi
      echo "${image}" >> "${workingdir}/images_to_scan.txt"
    ;;
    test | list )
      test_function
    ;;
    dist_git_copy )
      dist_git_copy
    ;;
    dist_git_inject )
      dist_git_inject
    ;;
    dist_git_branch_check )
      dist_git_branch_check
    ;;
    dist_git_migrate )
      dist_git_migrate
    ;;
    * )
      usage
      exit 2
    ;;
  esac
done

# Do post work for above Actions
case "$action" in
  dist_git_branch_check )
    if [ -f "${workingdir}/missing_branch.log" ]; then
      echo "dist-git repos missing branch ${branch}:"
      cat "${workingdir}/missing_branch.log"
    else
      echo "No repos found missing branch ${branch}"
    fi
  ;;
esac
}


# Do the work
do_work_each_package

# Do any post-work items that needs to be done.
case "$action" in
  build_container | build )
    wait_for_all_builds
    BUILD_FAIL=`cat ${workingdir}/logs/buildfailed | wc -l`
    THIS_TRY=`cat ${workingdir}/logs/try`
    if ! [ "${BUILD_FAIL}" == "0" ] && [ "${THIS_TRY}" == "1" ] ; then
      echo "===== Batch Attempt : ${THIS_TRY} FAILED BUILDS ====="
      echo
      let THIS_TRY=${THIS_TRY}+1
      echo ${THIS_TRY} > ${workingdir}/logs/try
      export packagelist=""
      for failed_package in `cat ${workingdir}/logs/buildfailed | cut -d':' -f3`
      do
        echo ${failed_package}
        sed -i "/::${failed_package}::/d" ${workingdir}/logs/buildfailed
        sed -i "/::${failed_package}::/d" ${workingdir}/logs/finished
        add_to_list ${failed_package}
      done
      echo ; echo "    Building Again" ; echo
      do_work_each_package
      wait_for_all_builds
      BUILD_FAIL=`cat ${workingdir}/logs/buildfailed | wc -l`
      THIS_TRY=`cat ${workingdir}/logs/try`
    fi
    PREBUILT_TOTAL=`cat ${workingdir}/logs/prebuilt | wc -l`
    BUILD_TOTAL=`cat ${workingdir}/logs/finished | wc -l`
    let BUILD_TOTAL=${BUILD_TOTAL}-1-${PREBUILT_TOTAL}
    SUCCESS_TOTAL=`cat ${workingdir}/logs/success | wc -l`
    echo "===== BUILD RESULTS ====="
    echo "Batch Attempts : ${THIS_TRY}"
    echo "Build Attempts : ${BUILD_TOTAL}"
    echo "Prebuilt       : ${PREBUILT_TOTAL}"
    echo "Good Builds : ${SUCCESS_TOTAL}"
    echo "Fail Builds : ${BUILD_FAIL}"

    cat ${workingdir}/logs/buildfailed | cut -d':' -f3
    if [ "${BUILD_FAIL}" != "0" ] ; then
      exit 1
    fi
  ;;
  push_images | push )
    BUILD_TOTAL=`cat ${workingdir}/logs/finished | wc -l`
    let BUILD_TOTAL=${BUILD_TOTAL}-1
    BUILD_FAIL=`cat ${workingdir}/logs/buildfailed | wc -l`
    let BUILD_SUCCESS=${BUILD_TOTAL}-${BUILD_FAIL}
    echo "===== PUSH RESULTS ====="
    echo "Total Pushes: ${BUILD_TOTAL}"
    echo "Good Pushes: ${BUILD_SUCCESS}"
    echo "Fail Pushes: ${BUILD_FAIL}"
    cat ${workingdir}/logs/buildfailed | cut -d':' -f3-4
  ;;
  scan_images )
    popd > /dev/null
    sudo atomic scan --scanner openscap \
      $(< "${workingdir}/images_to_scan.txt") \
      > scan.txt
  ;;
  compare_nodocker | compare_auto )
    if [ -s ${workingdir}/logs/mailfile ] ; then
      mail -s "[${MAJOR_RELEASE}] Dockerfile merge diffs" smunilla@redhat.com < ${workingdir}/logs/mailfile
      echo "===== GIT COMPARE DOCKEFILE CHANGES ====="
      cat ${workingdir}/logs/mailfile
      # echo "Exiting ..."
      # exit 1
    fi
  ;;
esac
