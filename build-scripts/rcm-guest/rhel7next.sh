#!/bin/bash
set -eu

BASE_DIR=/mnt/redhat
REMOTE_DIR=/srv/enterprise/rhel
LATEST_RHEL_COMPOSE=${BASE_DIR}/nightly/latest-RHEL-7
LATEST_EXTRAS=${BASE_DIR}/nightly/EXTRAS-RHEL-7.4/latest-EXTRAS-7-RHEL-7/compose/Server/x86_64/os
REPO_FILE=rhel7next.repo
MIRROR=use-mirror-upload.ops.rhcloud.com
rsync='rsync
--archive --hard-links --verbose --delete-after --progress --no-p --no-g
--omit-dir-times --chmod=Dug=rwX'

_reposync() {
    local repoid
    repoid=$1
    reposync \
        --config "${REPO_FILE}" \
        --download_path "${repoid}/" --repoid "${repoid}" \
        --arch x86_64 --download-metadata --downloadcomps --delete --norepopath
}

_createrepo_comp() {
    local item
    item=$1
    createrepo \
        --update --outputdir "${item}/" --group "${item}/comps.xml" "${item}/"
}

_createrepo() {
    local item
    item=$1
    createrepo --update --outputdir "${item}/" "${item}/"
}

mkdir -p /mnt/rcm-guest/puddles/RHAOS/rhel7next/
cd /mnt/rcm-guest/puddles/RHAOS/rhel7next/
cat > rhel7next.repo <<-'EOF'
	[rhel-7-fast-datapath-rpms]
	name = Red Hat Enterprise Linux 7 Fast Datapath
	baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/fast-datapath/os/
	enabled = 0
	gpgcheck = 0

	[rhel-7-fast-datapath-htb-rpms]
	name = Red Hat Enterprise Linux 7 Fast HTB Datapath
	baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/htb/rhel/server/7/x86_64/fast-datapath/os/
	enabled = 0
	gpgcheck = 0

	[rhel-7-server-ansible-2.4-rpms]
	name = Red Hat Ansible Engine 2.4 RPMs for Red Hat Enterprise Linux 7 Server
	baseurl = http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.4/os/
	enabled = 0
	gpgcheck = 0

	[rhel-7-server-ose-3.4-rpms]
	name=rhel-7-server-ose-3.4-rpms
	baseurl=http://pulp.dist.prod.ext.phx2.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ose/3.4/os/
	gpgcheck=0
	enabled=0
EOF
# rsync Server to os mirror
${rsync} \
    "${LATEST_RHEL_COMPOSE}/compose/Server/x86_64/os/" \
    "${MIRROR}:${REMOTE_DIR}/rhel7next/os/"
# rsync Server-Optional to os mirror
${rsync} \
    "${LATEST_RHEL_COMPOSE}/compose/Server-optional/x86_64/os/" \
    "${MIRROR}:${REMOTE_DIR}/rhel7next/optional/"
# rsync Server-Extras to os mirror
${rsync} \
    "${LATEST_EXTRAS}/" \
    "${MIRROR}:${REMOTE_DIR}/rhel7next/extras/"
# reposync repos
_reposync rhel-7-fast-datapath-rpms
_reposync rhel-7-fast-datapath-htb-rpms
_reposync rhel-7-server-ose-3.4-rpms
_reposync rhel-7-server-ansible-2.4-rpms
# Rebuild repos with comp files
_createrepo_comp "${PWD}/rhel-7-fast-datapath-rpms"
_createrepo_comp "${PWD}/rhel-7-fast-datapath-htb-rpms"
_createrepo_comp "${PWD}/rhel-7-server-ansible-2.4-rpms"
# Rebuild repos without comp files
_createrepo "${PWD}/rhel-7-server-ose-3.4-rpms"
# rsync repos to os mirror
${rsync} \
    rhel-7-{fast-datapath{,-htb},server-ose-3.4,server-ansible-2.4}-rpms \
    "${MIRROR}:${REMOTE_DIR}/"
# push to all geos
ssh "${MIRROR}" /usr/local/bin/push.enterprise.sh -v
