FROM centos:7
RUN yum -y install epel-release \
    && pkgs='git golang tito' \
    && yum -y install $pkgs \
    && rpm -q $pkgs
