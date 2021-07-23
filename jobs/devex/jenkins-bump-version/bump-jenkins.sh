#!/bin/bash
set -euo pipefail

#https://updates.jenkins-ci.org/download/war/2.73.1/jenkins.war


JENKINS_DIST_GIT="jenkins"
USER_USERNAME="--user=ocp-build"
SCRIPTS_DIR="$(pwd)"

usage() {
    echo >&2
    echo "Usage `basename $0` <jenkins-war-version> <rhaos-branch>" >&2
    echo >&2
    echo " Example: ./bump-jenkins.sh 2.73.1 rhaos-3.7-rhel-7" >&2
    exit 1
}

# clone jenkins distgit
# switch to latest branch
setup_dist_git() {
  workingdir="$SCRIPTS_DIR/working"
  rm -rf $workingdir
  mkdir -p $workingdir/logs


  if ! klist &>${workingdir}/logs/${JENKINS_DIST_GIT}.output ; then
    echo "Error: Kerberos token not found." ;
    exit 1
  fi

  cd ${workingdir}
  REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg ${USER_USERNAME} clone "${JENKINS_DIST_GIT}" &>${workingdir}/logs/${JENKINS_DIST_GIT}.output
  if [ -d ${JENKINS_DIST_GIT} ] ; then
    cd ${JENKINS_DIST_GIT}
    REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg switch-branch "${BRANCH}" &>${workingdir}/logs/${JENKINS_DIST_GIT}.output
  else
    echo " Failed to clone package: ${JENKINS_DIST_GIT}"
    exit 1
  fi
}

# download jenkins war
prep_jenkins_war() {
    set -eu
    wget --no-verbose https://ftp.belnet.be/pub/jenkins/war-stable/${VERSION}/jenkins.war
    wget --no-verbose https://ftp.belnet.be/pub/jenkins/war-stable/${VERSION}/jenkins.war.sha256
    sha256sum --check jenkins.war.sha256
    mv jenkins.war jenkins.${UVERSION}.war
    rm jenkins.war.sha256
}

# update changelog
update_dist_git () {
  if [ ! -f *.spec ]; then
      echo "No .spec file found. Exiting.">/dev/stderr
      exit 1
  fi
  REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg new-sources jenkins.${UVERSION}.war
  $SCRIPTS_DIR/rpm-bump-version.sh "${UVERSION}"
}

# rhpkg commit
# rhpkg push
commit_and_push() {
  REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg commit -p -m "Update Jenkins war to ${VERSION}"
}

# rhpkg build
build_jenkins() {
  REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg build --skip-nvr-check
}

# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
  exit 1
fi

# Use timestamp to create a version differentiated by the current date. Without this,
# if 3.6 uses Jenkins X.Y and then 3.7 tries to, it would find the build
# already complete and fail.
TSTAMP="$(date +%s)"

VERSION="$1"
UVERSION="$VERSION.$TSTAMP"
BRANCH="$2"

setup_dist_git
prep_jenkins_war
update_dist_git
commit_and_push
build_jenkins
