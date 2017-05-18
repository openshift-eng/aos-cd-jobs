#!/bin/bash

set -o errexit 
set -o nounset 
set -o pipefail 
set -o xtrace

cd /data/src/github.com/openshift/openshift-ansible
last_tag="$( git describe --tags --abbrev=0 --exact-match HEAD )"
last_commit="$( git log -n 1 --pretty=%h )"
sudo yum install -y "atomic-openshift-utils${last_tag/openshift-ansible/}.git.0.${last_commit}.el7"
