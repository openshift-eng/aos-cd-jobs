FROM centos:7
COPY rel-eng.repo /etc/yum.repos.d/
RUN yum -y install epel-release \
    && pkgs='brewkoji git golang krb5-workstation nss_wrapper rhpkg tito' \
    && yum -y install $pkgs \
    && rpm -q $pkgs
RUN curl 'https://password.corp.redhat.com/legacy.crt' \
        > /etc/pki/ca-trust/source/anchors/Red_Hat_IS_CA.crt \
    && update-ca-trust
COPY krb5.conf /etc/
COPY ssh_known_hosts /etc/ssh/
