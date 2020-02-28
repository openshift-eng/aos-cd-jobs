FROM registry.access.redhat.com/openshift3/jenkins-slave-base-rhel7:v3.11
USER root
RUN curl -sfL https://password.corp.redhat.com/RH-IT-Root-CA.crt \
        -o /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt \
    && update-ca-trust
COPY openshift-pipelines/images/repos/ /etc/yum.repos.d/
RUN yum remove -y subscription-manager \
    && yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm \
    && yum clean all
RUN yum install -y \
        krb5-workstation git rsync koji tito \
        gcc \
        git \
        jq \
        krb5-devel \
        libcurl-devel \
        libgit2 \
        openssl-devel \
        rpm-devel \
        python3 python3-devel python3-pip python36-certifi \
        koji brewkoji \
        rhpkg \
    && yum clean all

RUN pip3 install -U koji tox twine requests>=2.20 setuptools wheel codecov rh-doozer rh-elliott rh-ocp-build-data-validator
USER 1001
