#!/bin/bash

set -o errexit 
set -o nounset 
set -o pipefail 
set -o xtrace

cd /data/src/github.com/openshift/openshift-ansible

tito_tmp_dir="tito"
mkdir -p "${tito_tmp_dir}"
tito tag --offline --accept-auto-changelog
tito build --output="${tito_tmp_dir}" --rpm --test --offline --quiet
createrepo "${tito_tmp_dir}/noarch"

cat << EOR > ./openshift-ansible-local-release.repo
[openshift-ansible-local-release]
baseurl = file://$( pwd )/${tito_tmp_dir}/noarch
gpgcheck = 0
name = OpenShift Ansible Release from Local Source
EOR

sudo cp ./openshift-ansible-local-release.repo /etc/yum.repos.d
