#!/bin/bash
set -euo pipefail

#https://updates.jenkins-ci.org/download/war/2.73.1/jenkins.war


JENKINS_DIST_GIT="jenkins"

usage() {
    echo >&2
    echo "Usage `basename $0` <jenkins-war-version> <branch>" >&2
    echo >&2
    echo " Example: ./bump-jenkins.sh 2.73.1 rhaos-3.7-rhel-7" >&2
    exit 1
}

# clone jenkins distgit
# switch to latest branch 
setup_dist_git() {
  workingdir=$(dirname $(realpath $0))/working
  rm -rf $workingdir
  mkdir -p $workingdir/logs


  if ! klist &>${workingdir}/logs/${JENKINS_DIST_GIT}.output ; then
    echo "Error: Kerberos token not found." ; popd &>${workingdir}/logs/${JENKINS_DIST_GIT}.output ; exit 1
  fi

  cd ${workingdir}
  rhpkg ${USER_USERNAME} clone "${JENKINS_DIST_GIT}" &>${workingdir}/logs/${JENKINS_DIST_GIT}.output
  if [ -d ${JENKINS_DIST_GIT} ] ; then
    cd ${JENKINS_DIST_GIT}
    pushd ${JENKINS_DIST_GIT} >${workingdir}/logs/${JENKINS_DIST_GIT}.output
    rhpkg switch-branch "${BRANCH}" &>${workingdir}/logs/${JENKINS_DIST_GIT}.output
    popd >${workingdir}/logs/${JENKINS_DIST_GIT}.output
  else
    echo " Failed to clone package: ${JENKINS_DIST_GIT}"
  fi
}

# download jenkins war
prep_jenkins_war() {
    wget https://updates.jenkins-ci.org/download/war/${VERSION}/jenkins.war
    mv jenkins.war jenkins.${VERSION}.war
}

# update changelog
update_dist_git () {
  rhpkg new-sources jenkins.${VERSION}.war
  tito tag --offline --use-version="${VERSION}" --changelog="Update to ${VERSION}"
}

# rhpkg commit
# rhpkg push
commit_and_push() {
  rhpkg commit -p -m "Update Jenkins war to ${VERSION}"
}

# rhpkg build
build_jenkins() {
  rhpkg build
}

# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
  exit 1
fi

VERSION="$1"
BRANCH="$2"

setup_dist_git
prep_jenkins_war
update_dist_git