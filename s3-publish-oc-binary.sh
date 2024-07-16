#!/bin/bash
set -eux

PLASHET_DIR=$1
OSE_VERSION=$2
VERSION=$3


rpm_path() {
    echo "${PLASHET_DIR}/${arch}/os/Packages"
}

rpm_name() {
    echo -n "${RPM}"
    [[ "${arch}" == x86_64 ]] && printf %s -redistributable
    printf %s "-${VERSION}"
}

extract() {
    local arch rpm
    mkdir macosx windows
    for arch in x86_64 ${ARCH}; do
        rpm=$(echo "$(rpm_path)/"*/"$(rpm_name)"*)
        if [[ "${arch}" != x86_64 && ! -e "${rpm}" ]]; then continue; fi
        mkdir "${arch}"
        if [[ "${arch}" != x86_64 ]]; then
            rpm2cpio "${rpm}" | cpio -idm --quiet ./usr/bin/oc
            mv usr/bin/oc "${arch}"
        else
            rpm2cpio "${rpm}" \
                | cpio -idm --quiet \
                    ./usr/share/${PKG}/{linux,macosx}/oc \
                    ./usr/share/${PKG}/windows/oc.exe
            mv usr/share/${PKG}/linux/oc x86_64/
            mv usr/share/${PKG}/macosx/oc macosx/
            mv usr/share/${PKG}/windows/oc.exe windows/
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

PKG=${4:-atomic-openshift}
RPM=${PKG}-clients
ARCH='aarch64 ppc64le s390x'
TMPDIR=$PWD/tmp-rpm-extract
rm -rf $TMPDIR
mkdir -p $TMPDIR
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

aws s3 sync --no-progress --quiet --delete --exact-timestamps ${OUTDIR}/ s3://art-srv-enterprise/pub/openshift-v3/clients/${VERSION}/
aws s3 sync --no-progress --quiet --delete --exact-timestamps ${OUTDIR}/ s3://art-srv-enterprise/pub/openshift-v3/clients/${VERSION}/ --profile cloudflare --endpoint-url ${CLOUDFLARE_ENDPOINT}
