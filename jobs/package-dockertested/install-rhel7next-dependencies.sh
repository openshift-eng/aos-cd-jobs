#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

sudo yum --disablerepo=\* --enablerepo=rhel7next\* install -y "${@}"