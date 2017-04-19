#!/bin/sh
set -eux

OSE_VERSION=$1
VERSION=$2
rpm=/mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/$OSE_VERSION/latest/x86_64
rpm=$rpm/os/Packages/atomic-openshift-clients-redistributable-$VERSION
rpm=$(echo "$rpm"*)
tmpdir=$(mktemp -dt ocbinary.XXXXXXXXXX)
trap "rm -rf '$tmpdir'" EXIT INT TERM
mkdir -p "$tmpdir/$VERSION/"{linux,macosx,windows}
cd "$tmpdir"
rpm2cpio "$rpm" | cpio -idm --quiet
cd "$tmpdir/usr/share/atomic-openshift"
outdir=$tmpdir/$VERSION
tar --owner 0 --group 0 -C linux/ -zc oc -f "$outdir/linux/oc.tar.gz"
tar --owner 0 --group 0 -C macosx/ -zc oc -f "$outdir/macosx/oc.tar.gz"
zip --quiet --junk-path - windows/oc.exe > "$outdir/windows/oc.zip"
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "$outdir" \
    use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v3/clients/
ssh -l jenkins_aos_cd_bot -o StrictHostKeychecking=no \
    use-mirror-upload.ops.rhcloud.com \
    /usr/local/bin/push.pub.sh openshift-v3 -v
