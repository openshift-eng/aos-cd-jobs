#!/usr/bin/env bash

halp() {
  local program
  program="$(basename "$0")"
  cat <<-EOHALP
	$program: Build base images by creating commits in openshift-enterprise-base, and rhpkg build them
	Takes configuration from pullspecs.yaml. <image-key> Needs to be a key in pullspec.yml.
	
  Synopsis:
	  $program [-h|--help] | [-d|--dry-run] <image-key> [<rpm>...]

  Examples:
    distgit.sh -d elasticsearch

    for i in \$(yq -r 'keys[]' pullspecs.yaml); do ./distgit.sh -d \$i; done
EOHALP
}

pullspec() {
  local tag package nvr

  if yq -re --arg target "$target" '.[$target].pullspec | select(. != null)' pullspecs.yaml 2>/dev/null; then
    return
  fi

  tag="$(
    yq -re --arg target "$target" '.[$target].brew_tag' pullspecs.yaml
  )"

  package="$(
    yq -re --arg target "$target" '.[$target].package' pullspecs.yaml
  )"

  nvr="$(
    brew call --json-output listTagged "$tag" latest=true package="$package" | jq -re '.[0].nvr'
  )"

  # input: nvr
  # output: registry-proxy.engineering.redhat.com/rh-osbs/rhscl-nodejs-10-rhel7:1-38
  brew call --json-output getBuild "$nvr" | jq -re '.extra.image.index.pull[1]' 
}

user() {
  yq -re --arg target "$target" '.[$target].user' pullspecs.yaml
}

main() {
  local DRYRUN=0
  local user
  local pullspec

  if [[ $# == 0 ]]; then
    halp > /dev/stderr
    echo 'Need argument' >/dev/stderr
    exit 1
  fi

  export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
  USER_USERNAME="--user=ocp-build"
  
  for arg in "$@"; do
    case "$arg" in
      -d|--dry-run)
        DRYRUN=1
        ;;
      -h|--help)
        halp
        exit 0
        ;;
      *)
        target="$arg"
        ;;
    esac
    shift
  done

  user="$(user)"
  pullspec="$(pullspec)"

  if ((DRYRUN)); then
    echo "$target $pullspec $user"
  else
    build_common "$target" "$pullspec" "$user" $@
  fi
}

build_common() {
    img=$1; from=$2; user=$3
    shift; shift; shift
    TARGET_DIR=build-$img
    rm -rf ${TARGET_DIR}
    # for RHEL/UBI 8 and RHEL/UBI 7 we use different tags
    YUM_ARGS=""
    case "$img" in
        rhel8.2.els*) 
	  BRANCH="rhaos-4.2-rhel-8" ;;
        # for RHEL7 rhaos-4.0-rhel-7 is not in use, for RHEL8 rhaos-4.1-rhel-8 is not in use.
        ubi8*) 
	  BRANCH="rhaos-4.1-rhel-8" 
	  YUM_ARGS="--best --allowerasing"
	  ;;
        *) 
	  BRANCH="rhaos-4.0-rhel-7" ;;
    esac
    URL="http://pkgs.devel.redhat.com/cgit/containers/openshift-enterprise-base/plain/.oit/signed.repo?h=${BRANCH}"
    rhpkg --user=ocp-build clone --branch ${BRANCH} containers/openshift-enterprise-base ${TARGET_DIR}

    cd ${TARGET_DIR}
    echo "$img" > additional-tags
    case "$img" in
        # these base images only used in 3.11 and not available for s390x
        jboss.openjdk18.rhel7) z="#"; a="#" ;;
        elasticsearch|rhel7|rhscl.*.rhel7|ubi7) z=" "; a="#" ;;
        *) z=" "; a=" " ;;
    esac
    echo """---
platforms:
  only:
  - x86_64
  - ppc64le
$z - s390x
$a - aarch64
""" > container.yaml
    echo """
    FROM $from

    USER root
    RUN echo 'skip_missing_names_on_install=0' >> /etc/yum.conf \\
     && yum update $YUM_ARGS -y $@ \\
     && yum clean all
    USER $user

    LABEL \\
            com.redhat.component=\"openshift-enterprise-base-container\" \\
            name=\"openshift/ose-base\" \\
            version=\"v4.0\" \\
            release=\"$(date +%Y%m%d%H%M.$$)\"
    """ > Dockerfile
    git commit -am "updated $img container"
    git push
    # return the URL of the repo at this commit
    echo
    echo "${URL}&id=$(git rev-parse HEAD)"
}

set -euxo pipefail
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
