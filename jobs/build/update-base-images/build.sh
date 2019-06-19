#!/usr/bin/env bash

export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt

#➜  ~ docker run -it brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/jboss/openjdk18-rhel7:latest id
#uid=185(jboss) gid=185(jboss) groups=185(jboss)
#➜  ~ docker run -it  brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/elasticsearch:latest id
#uid=1000(elasticsearch) gid=1000(elasticsearch) groups=1000(elasticsearch)
#➜  ~  docker run -it brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888/ansible-runner:latest  id
#uid=0(root) gid=0(root) groups=0(root)
# `rhel7` is root 0`
# `nodejs6` is 1001`

TAG="rhaos-4.0-rhel-7"
URL="http://pkgs.devel.redhat.com/cgit/containers/openshift-enterprise-base/plain/.oit/signed.repo?h=${TAG}"
USER_USERNAME="--user=ocp-build"

build_common() {
    TARGET_DIR=build-$1
    rm -rf ${TARGET_DIR}
    rhpkg ${USER_USERNAME} clone --branch ${TAG} containers/openshift-enterprise-base ${TARGET_DIR}

    cd ${TARGET_DIR}
    echo "$1" > additional-tags
    echo """FROM $2

    USER root
    RUN yum update -y && yum clean all
    USER $3

    LABEL \\
            com.redhat.component=\"openshift-enterprise-base-container\" \\
            name=\"openshift/ose-base\" \\
            version=\"v4.0\" \\
            release=\"$(date +%Y%m%d%H%M)\"
    """ > Dockerfile
    git commit -am "updated $1 container"
    git push
    rhpkg  ${USER_USERNAME} container-build --repo-url ${URL}
}

case "$1" in
        ansible.runner)
            build_common $1 ansible-runner:latest 0
            ;;

        elasticsearch)
            build_common $1 elasticsearch:latest 1000
            ;;

        jboss.openjdk18.rhel7)
            build_common $1 jboss/openjdk18-rhel7:latest 185
            ;;
        rhscl.nodejs.6.rhel7)
            build_common $1 rhscl/nodejs-6-rhel7:6-53.1560797448 1001
            ;;
        rhel7)
            build_common $1 rhel7:7-released 0
            ;;
        *)
            echo $"Usage: $0 image_tag image_name"
            exit 1
            ;;
esac
