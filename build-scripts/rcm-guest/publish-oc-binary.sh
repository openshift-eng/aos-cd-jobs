#!/bin/bash
set -eux

rpm_name() {
    printf "${RPM}" "${arch}"
    [[ "${arch}" == x86_64 ]] && printf %s -redistributable
    printf %s "-${VERSION}"
}

extract() {
    local arch rpm
    mkdir macosx windows
    for arch in x86_64 ${ARCH}; do
        rpm=$(echo "$(rpm_name "${arch}")"*)
        if [[ "${arch}" != x86_64 && ! -e "${rpm}" ]]; then continue; fi
        mkdir "${arch}"
        if [[ "${arch}" != x86_64 ]]; then
            rpm2cpio "${rpm}" | cpio -idm --quiet ./usr/bin/oc
            mv usr/bin/oc "${arch}"
        else
            rpm2cpio "${rpm}" \
                | cpio -idm --quiet \
                    ./usr/share/atomic-openshift/{linux,macosx}/oc \
                    ./usr/share/atomic-openshift/windows/oc.exe
            mv usr/share/atomic-openshift/linux/oc x86_64/
            mv usr/share/atomic-openshift/macosx/oc macosx/
            mv usr/share/atomic-openshift/windows/oc.exe windows/
        fi
    done
}

pkg_tar() {
    local dir
    case "$1" in
        x86_64) dir=linux;;
        macosx) dir=macosx;;
        aarch64|ppc64le|s390x) dir=linux-${1};;
    esac
    mkdir "${OUTDIR}/${dir}"
    tar --owner 0 --group 0 -C "$1" -zc oc -f "${OUTDIR}/${dir}/oc.tar.gz"
}

OSE_VERSION=$1
VERSION=$2
RPM=/mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/${OSE_VERSION}/latest/%s
RPM=${RPM}/os/Packages/atomic-openshift-clients
ARCH='aarch64 ppc64le s390x'
TMPDIR=$(mktemp -dt ocbinary.XXXXXXXXXX)
trap "rm -rf '${TMPDIR}'" EXIT INT TERM
OUTDIR=${TMPDIR}/${VERSION}

cd "${TMPDIR}"
extract
mkdir "${OUTDIR}"
for arch in ${ARCH}; do [[ -e "${arch}" ]] && pkg_tar "${arch}"; done
pkg_tar x86_64
pkg_tar macosx
mkdir "${OUTDIR}/windows"
zip --quiet --junk-path - windows/oc.exe > "${OUTDIR}/windows/oc.zip"
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${OUTDIR}" \
    use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v3/clients/
ssh -l jenkins_aos_cd_bot -o StrictHostKeychecking=no \
    use-mirror-upload.ops.rhcloud.com \
    timeout 15m /usr/local/bin/push.pub.sh openshift-v3 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v3 -v || timeout 5m /usr/local/bin/push.pub.sh openshift-v3 -v
