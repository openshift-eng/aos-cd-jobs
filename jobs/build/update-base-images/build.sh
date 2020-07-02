#!/usr/bin/env bash

set -euxo pipefail

export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt

#➜  ~ docker run -it brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/jboss/openjdk18-rhel7:latest id
#uid=185(jboss) gid=185(jboss) groups=185(jboss)
#➜  ~ docker run -it  brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/elasticsearch:latest id
#uid=1000(elasticsearch) gid=1000(elasticsearch) groups=1000(elasticsearch)
#➜  ~  docker run -it brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/ansible-runner:latest  id
#uid=0(root) gid=0(root) groups=0(root)
# `rhel7` is root 0`
# `nodejs{6,10,12}` is 1001`

USER_USERNAME="--user=ocp-build"

build_common() {
    img=$1; from=$2; user=$3
    shift; shift; shift
    TARGET_DIR=build-$img
    rm -rf ${TARGET_DIR}
    # for RHEL/UBI 8 and RHEL/UBI 7 we use different tags
    case "$img" in
        # for RHEL7 rhaos-4.0-rhel-7 is not in use, for RHEL8 rhaos-4.1-rhel-8 is not in use.
        ubi8) BRANCH="rhaos-4.1-rhel-8" ;;
        *) BRANCH="rhaos-4.0-rhel-7" ;;
    esac
    URL="http://pkgs.devel.redhat.com/cgit/containers/openshift-enterprise-base/plain/.oit/signed.repo?h=${BRANCH}"
    rhpkg ${USER_USERNAME} clone --branch ${BRANCH} containers/openshift-enterprise-base ${TARGET_DIR}

    cd ${TARGET_DIR}
    echo "$img" > additional-tags
    case "$img" in
        # these base images only used in 3.11 and not available for s390x
        ansible.runner|jboss.openjdk18.rhel7) z="#" ;;
        *) z=" " ;;
    esac
    echo """---
platforms:
  only:
  - x86_64
  - ppc64le
$z - s390x
""" > container.yaml
    echo """
    FROM $from

    USER root
    RUN echo 'skip_missing_names_on_install=0' >> /etc/yum.conf \\
     && yum update -y $@ \\
     && yum clean all
    USER $user

    LABEL \\
            com.redhat.component=\"openshift-enterprise-base-container\" \\
            name=\"openshift/ose-base\" \\
            version=\"v4.0\" \\
            release=\"$(date +%Y%m%d%H%M)\"
    """ > Dockerfile
    git commit -am "updated $img container"
    git push
    rhpkg  ${USER_USERNAME} container-build --repo-url ${URL}
}

img=$1; shift
case "$img" in
    ansible.runner)
        build_common $img ansible-runner:1.2.0 0 $@
        ;;
    elasticsearch)
        build_common $img elasticsearch:latest 1000 $@
        ;;
    jboss.openjdk18.rhel7)
        build_common $img jboss/openjdk18-rhel7:latest 185 $@
        ;;
    rhscl.nodejs.6.rhel7)
        build_common $img rhscl/nodejs-6-rhel7:6-53.1580118007 1001 $@
        ;;
    rhscl.nodejs.10.rhel7)
        build_common $img rhscl/nodejs-10-rhel7:1-27.1584463517 1001 $@
        ;;
    rhscl.nodejs.12.rhel7)
        build_common $img rhscl/nodejs-12-rhel7:1-6.1582646197 1001 $@
        ;;
    rhscl.ruby.25.rhel7)
        build_common $img rhscl/ruby-25-rhel7:latest 1001 $@
        ;;
    rhscl.python.36.rhel7)
        build_common $img rhscl/python-36-rhel7:latest 1001 $@
        ;;
    rhel7)
        build_common $img rhel7:7-released 0 $@
        ;;
    ubi7)
        build_common $img ubi7:7-released 0 $@
        ;;
    ubi8)
        build_common $img ubi8:8-released 0 $@
        ;;
    *)
        echo $"Usage: $0 image_tag [package [...]]"
        exit 1
        ;;
esac
