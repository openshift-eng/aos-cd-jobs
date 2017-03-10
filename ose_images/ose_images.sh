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

set -o xtrace

## LOCAL VARIABLES ##
MASTER_RELEASE="3.6"
MAJOR_RELEASE="3.5"
DIST_GIT_BRANCH="rhaos-${MAJOR_RELEASE}-rhel-7"
#DIST_GIT_BRANCH="rhaos-3.2-rhel-7-candidate"
#DIST_GIT_BRANCH="rhaos-3.1-rhel-7"
SCRATCH_OPTION=""
BUILD_REPO="http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo"
COMMIT_MESSAGE=""
PULL_REGISTRY=brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888
#PULL_REGISTRY=rcm-img-docker01.build.eng.bos.redhat.com:5001
PUSH_REGISTRY=registry-push.ops.openshift.com
#PUSH_REGISTRY=registry.qe.openshift.com
ERRATA_ID="24510"
ERRATA_PRODUCT_VERSION="RHEL-7-OSE-${MAJOR_RELEASE}"
SCRIPT_HOME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

usage() {
  echo "Usage `basename $0` [action] <options>" >&2
  echo >&2
  echo "Actions:" >&2
  echo "  build_container :: Build containers in OSBS" >&2
  echo "  push_images     :: Push images to qe-registry" >&2
  echo "  compare_git     :: Compare dist-git Dockerfile and other files with those in git" >&2
  echo "  compare_nodocker :: Compare dist-git files with those in git.  Show but do not change Dockerfile changes" >&2
  echo "  update_docker   :: Update dist-git Dockerfile version, release, or rhel" >&2
  echo "  update_compare  :: Run update_docker, compare_update, then update_docker again" >&2
  echo "  update_errata   :: Update image errata with Docker images" >&2
  echo "  make_yaml       :: Print out yaml from Dockerfile for release" >&2
  echo "  list            :: Display full list of packages / images" >&2
  echo "  test            :: Display what packages would be worked on" >&2
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
  echo "  --group [group]     :: Which group list to use (base sti database deployer metrics logging jenkins misc all)" >&2
  echo "  --package [package] :: Which package to use e.g. openshift-enterprise-pod-docker" >&2
  echo "  --version [version] :: Change Dockerfile version e.g. 3.1.1.2" >&2
  echo "  --release [version] :: Change Dockerfile release e.g. 3" >&2
  echo "  --bump_release      :: Change Dockerfile release by 1 e.g. 3->4" >&2
  echo "  --rhel [version]    :: Change Dockerfile RHEL version e.g. rhel7.2:7.2-35 or rhel7:latest" >&2
  echo "  --branch [version]  :: Use a certain dist-git branch  default[${DIST_GIT_BRANCH}]" >&2
  echo "  --repo [Repo URL]   :: Use a certain yum repo  default[${BUILD_REPO}]" >&2
  echo "  --errata_id [id]      :: errata id to use  default[${ERRATA_ID}]" >&2
  echo "  --errata_pv [version] :: errata product version to use  default[${ERRATA_PRODUCT_VERSION}]" >&2
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
        add_to_list aos3-installation-docker
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
        add_to_list aos3-installation-docker
        add_to_list openshift-enterprise-docker
        add_to_list openshift-enterprise-dockerregistry-docker
        add_to_list openshift-enterprise-egress-router-docker
        add_to_list openshift-enterprise-keepalived-ipfailover-docker
        add_to_list openshift-enterprise-openvswitch-docker
        add_to_list aos-f5-router-docker
        add_to_list openshift-enterprise-deployer-docker
        add_to_list openshift-enterprise-haproxy-router-docker
        add_to_list openshift-enterprise-node-docker
        add_to_list openshift-enterprise-recycler-docker
        add_to_list openshift-enterprise-sti-builder-docker
        add_to_list openshift-enterprise-docker-builder-docker
        add_to_list logging-deployment-docker
        add_to_list metrics-deployer-docker
      fi
    ;;
    sti)
      add_to_list openshift-sti-base-docker
      add_to_list openshift-sti-nodejs-docker
      add_to_list openshift-sti-perl-docker
      add_to_list openshift-sti-php-docker
      add_to_list openshift-sti-python-docker
      add_to_list openshift-sti-ruby-docker
    ;;
    database)
      add_to_list openshift-mongodb-docker
      add_to_list openshift-mysql-docker
      add_to_list openshift-postgresql-docker
    ;;
    misc)
      add_to_list image-inspector-docker
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] ; then
        add_to_list registry-console-docker
      fi
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
      add_to_list openshift-jenkins-docker
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] && [ ${MAJOR_RELEASE} != "3.3" ] ; then
        add_to_list openshift-jenkins-2-docker
      fi
      add_to_list jenkins-slave-base-rhel7-docker
      add_to_list jenkins-slave-maven-rhel7-docker
      add_to_list jenkins-slave-nodejs-rhel7-docker
    ;;
    jenkins-plain )
      add_to_list openshift-jenkins-docker
      if [ ${MAJOR_RELEASE} != "3.1" ] && [ ${MAJOR_RELEASE} != "3.2" ] && [ ${MAJOR_RELEASE} != "3.3" ] ; then
        add_to_list openshift-jenkins-2-docker
      fi
    ;;
    jenkins-slaves )
      add_to_list jenkins-slave-base-rhel7-docker
      add_to_list jenkins-slave-maven-rhel7-docker
      add_to_list jenkins-slave-nodejs-rhel7-docker
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
    oso)
      add_group_to_list oso-accountant-docker
      add_group_to_list oso-notifications-docker
      add_group_to_list oso-reconciler-docker
      add_group_to_list oso-user-analytics-docker
    ;;
  esac
}

setup_dist_git() {
  if ! klist &>/dev/null ; then
    echo "Error: Kerberos token not found." ; popd &>/dev/null ; exit 1
  fi
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_dist_git **"
    echo " container:  ${container} branch: ${branch} "
  fi
  rhpkg ${USER_USERNAME} clone "${container}" &>/dev/null
  pushd ${container} >/dev/null
  rhpkg switch-branch "${branch}" &>/dev/null
  popd >/dev/null
}

setup_dockerfile() {
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_dockerfile **"
    echo " container:  ${container} branch: ${branch} "
  fi
  mkdir -p "${container}" &>/dev/null
  pushd ${container} >/dev/null
  wget -q -O Dockerfile http://dist-git.app.eng.bos.redhat.com/cgit/rpms/${container}/plain/Dockerfile?h=${branch} &>/dev/null
  test_file="$(head -n 1 Dockerfile | awk '{print $1}')"
  if [ "${test_file}" == "" ] ; then
    rm -f Dockerfile
    wget -q -O Dockerfile http://dist-git.app.eng.bos.redhat.com/cgit/rpms/${container}/plain/Dockerfile.product?h=${branch} &>/dev/null
  elif [ "${test_file}" == "Dockerfile.product" ] || [ "${test_file}" == "Dockerfile.rhel7" ] ; then
    rm -f Dockerfile
    wget -q -O Dockerfile http://dist-git.app.eng.bos.redhat.com/cgit/rpms/${container}/plain/${test_file}?h=${branch} &>/dev/null
  fi
  popd >/dev/null
}

setup_git_repo() {
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ** setup_git_repo **"
    echo " git_repo: ${git_repo} "
    echo " git_path: ${git_path} "
    echo " git_branch: ${git_branch} "
  fi
  pushd "${workingdir}" >/dev/null
  git clone -q ${git_repo} 2>/dev/null
  pushd "${git_path}" >/dev/null
  git checkout ${git_branch} 2>/dev/null
  popd >/dev/null
  popd >/dev/null

}

check_builds() {
  pushd "${workingdir}/logs" >/dev/null
  ls -1 *buildlog | while read line
  do
    if grep -q -e "buildContainer (noarch) failed" -e "server startup error" ${line} ; then
      package=`echo ${line} | cut -d'.' -f1`
      echo "=== ${package} IMAGE BUILD FAILED ==="
      mv ${line} ${package}.watchlog done/
      echo "::${package}::" >> ${workingdir}/logs/finished
      sed -i "/::${package}::/d" ${workingdir}/logs/working
      if grep -q -e "already exists" ${line} ; then
        grep -e "already exists" ${line} | cut -d':' -f4-
        echo "Package with same NVR has already been built"
        echo "::${package}::" >> ${workingdir}/logs/prebuilt
      else
        echo "::${package}::" >> ${workingdir}/logs/buildfailed
        echo "Failed logs"
        ls -1 ${workingdir}/logs/done/${package}.*
        cp -f ${workingdir}/logs/done/${package}.* ${workingdir}/logs/failed-logs/
      fi
    else
      if grep -q -e "completed successfully" ${line} ; then
        package=`echo ${line} | cut -d'.' -f1`
        echo "==== ${package} IMAGE COMPLETED ===="
        # Only doing false positives, but leave code incase we need something similar
        #if grep "No package" ${package}.watchlog ; then
        #  echo "===== ${package}: ERRORS IN COMPLETED IMAGE see above ====="
        #  echo "::${package}::" >> ${workingdir}/logs/buildfailed
        #fi
        echo "::${package}::" >> ${workingdir}/logs/finished
        echo "::${package}::" >> ${workingdir}/logs/success
        sed -i "/::${package}::/d" ${workingdir}/logs/working
        mv ${line} ${package}.watchlog done/
      fi
    fi
  done
  popd >/dev/null
}

wait_for_all_builds() {
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
    rhpkg ${USER_USERNAME} container-build ${SCRATCH_OPTION} --repo ${BUILD_REPO} >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-unsigned-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-unsigned-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-unsigned-errata-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-unsigned-errata-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-signed-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-container-signed-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-errata-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-errata-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-signed-building.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    #rhpkg container-build --repo http://file.rdu.redhat.com/tdawson/repo/aos-signed-latest.repo >> ${workingdir}/logs/${container}.buildlog 2>&1 &
    echo -n "  Waiting for build to start ."
    sleep 10
    taskid=`grep 'Watching tasks' ${workingdir}/logs/${container}.buildlog | awk '{print $1}' | sort -u`
    while [ "${taskid}" == "" ]
    do
      echo -n "."
      sleep 10
      taskid=`grep 'Watching tasks' ${workingdir}/logs/${container}.buildlog | awk '{print $1}' | sort -u`
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
      sed -i -e "s/FROM \(.*\):v.*/FROM \1:${version_version}/" ${line}
    fi
    if [ "${update_release}" == "TRUE" ] ; then
      sed -i -e "s/release=\".*\"/release=\"${release_version}\"/" ${line}
    fi
    if [ "${bump_release}" == "TRUE" ] ; then
      old_release_version=$(grep release= ${line} | cut -d'=' -f2 | cut -d'"' -f2 )
      let new_release_version=$old_release_version+1
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

show_git_diffs() {
  pushd "${workingdir}/${container}" >/dev/null
  if ! [ "${git_style}" == "dockerfile_only" ] ; then
    echo "  ---- Checking files changed, added or removed ----"
    extra_check=$(diff --brief -r ${workingdir}/${container} ${workingdir}/${git_path} | grep -v -e Dockerfile -e additional-tags -e git -e osbs )
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
        git rm ${myold_dir_file_trim}
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
  diff --label Dockerfile --label ${git_path}/Dockerfile -u0 Dockerfile ${workingdir}/${git_path}/${git_dockerfile} >> .osbs-logs/Dockerfile.diff.new
  if ! [ -f .osbs-logs/Dockerfile.diff ] ; then
    touch .osbs-logs/Dockerfile.diff
  fi
  newdiff=`diff -u0 .osbs-logs/Dockerfile.diff .osbs-logs/Dockerfile.diff.new | grep -v -e Dockerfile -e '@@' -e release= -e version= -e 'FROM '`
  if [ "${newdiff}" == "" ] ; then
    mv -f .osbs-logs/Dockerfile.diff.new .osbs-logs/Dockerfile.diff 2> /dev/null
    git add .osbs-logs/Dockerfile.diff 2> /dev/null
  fi
  if ! [ "${newdiff}" == "" ] || ! [ "${extra_check}" == "" ] ; then
    echo "${newdiff}"
    echo " "
    echo "Changes occured "
    if [ "${FORCE}" == "TRUE" ] ; then
      echo "  Force Option Selected - Assuming Continue"
      mv -f .osbs-logs/Dockerfile.diff.new .osbs-logs/Dockerfile.diff ; git add .osbs-logs/Dockerfile.diff ; rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
    else
      echo "  To view/modify changes, go to: ${workingdir}/${container}"
      echo "(c)ontinue [rhpkg commit], (i)gnore, (q)uit [exit script] : "
      read choice_raw < /dev/tty
      choice=$(echo "${choice_raw}" | awk '{print $1}')
      case ${choice} in
        c | C | continue )
          mv -f .osbs-logs/Dockerfile.diff.new .osbs-logs/Dockerfile.diff 2> /dev/null
          git add .osbs-logs/Dockerfile.diff 2> /dev/null
          rhpkg ${USER_USERNAME} commit -p -m "${COMMIT_MESSAGE} ${version_version} ${release_version} ${rhel_version}" > /dev/null
          ;;
        i | I | ignore )
          rm -f .osbs-logs/Dockerfile.diff.new
          ;;
        q | Q | quit )
          break
          ;;
        * )
          echo "${choice} not and option.  Assuming ignore"
          rm -f .osbs-logs/Dockerfile.diff.new
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
    extra_check=$(diff --brief -r ${workingdir}/${container} ${workingdir}/${git_path} | grep -v -e Dockerfile -e additional-tags -e git -e osbs )
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
        git rm ${myold_dir_file_trim}
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
  diff --label Dockerfile --label ${git_path}/Dockerfile -u0 Dockerfile ${workingdir}/${git_path}/${git_dockerfile} >> .osbs-logs/Dockerfile.diff.new
  if ! [ -f .osbs-logs/Dockerfile.diff ] ; then
    touch .osbs-logs/Dockerfile.diff
  fi
  newdiff=`diff -u0 .osbs-logs/Dockerfile.diff .osbs-logs/Dockerfile.diff.new | grep -v -e Dockerfile -e '@@' -e release= -e version= -e 'FROM '`
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
      case ${choice} in
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

function push_image {
   docker push $1
   if [ $? -ne 0 ]; then
     echo "OH NO!!! There was a problem pushing the image."
     echo "::BAD_PUSH ${container} ${1}::" >> ${workingdir}/logs/buildfailed
     sed -i "/::${1}::/d" ${workingdir}/logs/working
     exit 1
   fi
   echo "::${1}::" >> ${workingdir}/logs/finished
   sed -i "/::${1}::/d" ${workingdir}/logs/working
}

start_push_image() {
  pushd "${workingdir}/${container}" >/dev/null
  package_name=`grep " name=" Dockerfile | cut -d'"' -f2`
  if ! [ "${update_version}" == "TRUE" ] ; then
    version_version=`grep version= Dockerfile | cut -d'"' -f2`
  fi
  if ! [ "${update_release}" == "TRUE" ] ; then
    release_version=`grep release= Dockerfile | cut -d'"' -f2`
  fi
  START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
  echo "====================================================" >>  ${workingdir}/logs/push.image.log
  echo "  ${container} ${package_name}:${version_version}-${release_version}" | tee -a ${workingdir}/logs/push.image.log
  echo "    START: ${START_TIME}" | tee -a ${workingdir}/logs/push.image.log
  echo | tee -a ${workingdir}/logs/push.image.log
  # Do our pull
  docker pull ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version}
  if [ $? -ne 0 ]; then
    echo "OH NO!!! There was a problem pulling the image."
    echo "::BAD_PULL ${container} ${package_name}:${version_version}-${release_version}::" >> ${workingdir}/logs/buildfailed
    sed -i "/::${container}::/d" ${workingdir}/logs/working
  else
    echo | tee -a ${workingdir}/logs/push.image.log
    # Work through what tags to push to, one group at a time
    for current_tag in ${tag_list} ; do
      case ${current_tag} in
        default )
          # Full name - <name>:<version>-<release>
          echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:${version_version}-${release_version}" | tee -a ${workingdir}/logs/push.image.log
          docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:${version_version}-${release_version} | tee -a ${workingdir}/logs/push.image.log
          echo | tee -a ${workingdir}/logs/push.image.log
          push_image ${PUSH_REGISTRY}/${package_name}:${version_version}-${release_version} | tee -a ${workingdir}/logs/push.image.log
          echo | tee -a ${workingdir}/logs/push.image.log
          # Name and Version - <name>:<version>
          if ! [ "${NOVERSIONONLY}" == "TRUE" ] ; then
            echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:${version_version}" | tee -a ${workingdir}/logs/push.image.log
            docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:${version_version} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
            push_image ${PUSH_REGISTRY}/${package_name}:${version_version} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
          fi
          # Latest - <name>:latest
          if ! [ "${NOTLATEST}" == "TRUE" ] ; then
            echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:latest" | tee -a ${workingdir}/logs/push.image.log
            docker tag  -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:latest | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
            push_image ${PUSH_REGISTRY}/${package_name}:latest | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
        single-v )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim="v${MAJOR_RELEASE}"
            echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:${version_trim}" | tee -a ${workingdir}/logs/push.image.log
            docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
            push_image ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
        all-v )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim_list="v3.1 v3.2 v3.3 v3.4"
            for version_trim in ${version_trim_list} ; do
              echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:${version_trim}" | tee -a ${workingdir}/logs/push.image.log
              docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
              echo | tee -a ${workingdir}/logs/push.image.log
              push_image ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
              echo | tee -a ${workingdir}/logs/push.image.log
            done
          fi
        ;;
        three-only )
          if ! [ "${NOCHANNEL}" == "TRUE" ] ; then
            version_trim=`echo ${version_version} | sed 's|v||g' | cut -d'.' -f-3`
            echo "  TAG/PUSH: ${PUSH_REGISTRY}/${package_name}:${version_trim}" | tee -a ${workingdir}/logs/push.image.log
            docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
            push_image ${PUSH_REGISTRY}/${package_name}:${version_trim} | tee -a ${workingdir}/logs/push.image.log
            echo | tee -a ${workingdir}/logs/push.image.log
          fi
        ;;
      esac
    done
    if ! [ "${alt_name}" == "" ] ; then
      if [ "${VERBOSE}" == "TRUE" ] ; then
        echo "----------"
        echo "docker tag ${PULL_REGISTRY}/${package_name}:${package_name}:${version_version} ${PUSH_REGISTRY}/${alt_name}:${version_version}"
        echo "push_image ${PUSH_REGISTRY}/${alt_name}:${version_version}"
        echo "----------"
      fi
      echo "  TAG/PUSH: ${PUSH_REGISTRY}/${alt_name}:${version_version} " | tee -a ${workingdir}/logs/push.image.log
      docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${alt_name}:${version_version} | tee -a ${workingdir}/logs/push.image.log
      echo | tee -a ${workingdir}/logs/push.image.log
      push_image ${PUSH_REGISTRY}/${alt_name}:${version_version} | tee -a ${workingdir}/logs/push.image.log
      echo | tee -a ${workingdir}/logs/push.image.log
      if ! [ "${NOTLATEST}" == "TRUE" ] ; then
        echo "  TAG/PUSH: ${PUSH_REGISTRY}/${alt_name}:latest " | tee -a ${workingdir}/logs/push.image.log
        docker tag -f ${PULL_REGISTRY}/${package_name}:${version_version}-${release_version} ${PUSH_REGISTRY}/${alt_name}:latest | tee -a ${workingdir}/logs/push.image.log
        echo | tee -a ${workingdir}/logs/push.image.log
        push_image ${PUSH_REGISTRY}/${alt_name}:latest | tee -a ${workingdir}/logs/push.image.log
        echo | tee -a ${workingdir}/logs/push.image.log
      fi
    fi
  fi
  STOP_TIME=$(date +"%Y-%m-%d %H:%M:%S")
  echo | tee -a ${workingdir}/logs/push.image.log
  echo "FINISHED: ${container} START TIME: ${START_TIME}  STOP TIME: ${STOP_TIME}" | tee -a ${workingdir}/logs/push.image.log
  echo | tee -a ${workingdir}/logs/push.image.log
  popd >/dev/null
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
    compare_git | git_compare | compare_nodocker | update_docker | docker_update | build_container | build | make_yaml | push_images | push | update_compare | update_errata | test)
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
      if [ "${MASTER_RELEASE}" == "${MAJOR_RELEASE}" ] ; then
        export git_branch="master"
      else
        export git_branch="enterprise-${MAJOR_RELEASE}"
      fi
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
    compare_nodocker )
      if [ "${MASTER_RELEASE}" == "${MAJOR_RELEASE}" ] ; then
        export git_branch="master"
      else
        export git_branch="enterprise-${MAJOR_RELEASE}"
      fi
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
      if [ "${MASTER_RELEASE}" == "${MAJOR_RELEASE}" ] ; then
        export git_branch="master"
      else
        export git_branch="enterprise-${MAJOR_RELEASE}"
      fi
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
      export alt_name=$(echo "${dict_image_name[${container}]}" | awk '{print $2}')
      export tag_list="${dict_image_tags[${container}]}"
      if ! [ "${brew_name}" == "" ] ; then
        echo "::${container}::" >> ${workingdir}/logs/working
        push_images
      else
        echo "  Skipping ${container} - Image for building only"
      fi
    ;;
    test | list )
      test_function
    ;;
    * )
      usage
      exit 2
    ;;
  esac
done
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
  compare_nodocker )
    if [ -s ${workingdir}/logs/mailfile ] ; then
      mail -s "[${MAJOR_RELEASE}] Dockerfile merge diffs" tdawson@redhat.com,smunilla@redhat.com < ${workingdir}/logs/mailfile
      echo "===== GIT COMPARE FAIL ====="
      cat ${workingdir}/logs/mailfile
      echo "Exiting ..."
      exit 1
    fi
  ;;
esac
