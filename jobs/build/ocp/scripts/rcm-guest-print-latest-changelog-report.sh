#!/bin/sh
set -e

# Must be run from rcm-guest or system with /mnt/rcm-guest mount

OSE_VERSION=$1

if [ -z "$OSE_VERSION" ]; then
    echo "OSE Version (e.g. 3.6) must be specified as first parameter"
    exit 1
fi

pkgs=/mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/$OSE_VERSION/latest/x86_64/os/Packages
openshift_rpm=$(ls "${pkgs}/atomic-openshift-$OSE_VERSION"*.rpm)
ansible_rpm=$(ls "${pkgs}/openshift-ansible-$OSE_VERSION"*.rpm)

echo "===Atomic OpenShift changelog snippet==="
rpm -q --changelog -p ${openshift_rpm} 2>&1 | head -n 100
echo ...truncated...

echo
echo
echo "===OpenShift Ansible changelog snippet==="
rpm -q --changelog -p ${ansible_rpm} 2>&1 | head -n 100
echo ...truncated...
