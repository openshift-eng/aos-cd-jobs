#!/usr/bin/env bash

if [[ -z "$1" ]]; then
	echo "Syntax: <major>.<minor>"
	exit 1
fi

set -eu

cat > rhel-7.conf <<EOF
[main]
cachedir=${PWD}/cache/
keepcache=0
debuglevel=2
logfile=${PWD}/rhe-7-yum.log
exactarch=1
obsoletes=1
gpgcheck=1
plugins=1
installonly_limit=3

[rhel-server-optional-rpms]
name = rhel-server-optional-rpms
baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/optional/os/
gpgcheck = 0
enabled = 1

[rhel-server-extras-rpms]
name = rhel-server-extras-rpms
baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/extras/os/
enabled = 1
gpgcheck = 0

[rhel-server-rpms]
name = rhel-server-rpms
baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/os/
enabled = 1
gpgcheck = 0

[rhel-server-ose-rpms]
name = rhel-server-ose-rpms
baseurl = http://download.lab.bos.redhat.com/rcm-guest/puddles/RHAOS/plashets/${1}/building/x86_64/os
enabled = 1
gpgcheck = 0

EOF

# clear anything that might already exist
TARGET_DIR="${1}-beta"
rm -rf cache "${TARGET_DIR}"
yumdownloader -c rhel-7.conf --resolve --destdir="${TARGET_DIR}"\
 criu\
 runc\
 cri-o\
 cri-tools\
 skopeo\
 openshift-clients\
 openshift-hyperkube\
 openshift-clients-redistributable\
 slirp4netns

rm -rf cache  # clean cache file when it completes
echo "${TARGET_DIR} contains the files to mirror"
echo "Make sure to run createrepo on the mirror and /usr/local/bin/push.pub.sh"
