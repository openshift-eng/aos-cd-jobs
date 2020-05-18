#!/bin/bash
set -euxo pipefail

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"
TKN_VERSION=${1}
TKN_URL=${2}

# check if already exists
### TODO: figure out why the script exits regardless of test result when this is uncommented:
#if ssh ${SSH_OPTS} "[ -d /srv/pub/openshift-v4/clients/pipeline/${TKN_VERSION} ]"
#then
#    echo "Already have latest version"
#    exit 0
#fi
echo "Fetching OpenShift Pipelines Client ${TKN_VERSION} binaries"

OUTDIR=$(mktemp -dt tknbinary.XXXXXXXXXX)
trap "rm -rf '${OUTDIR}'" EXIT INT TERM

pkg_tar() {
    local dir
    case "$1" in
        x86_64) dir=linux;;
        macos) dir=macos;;
        aarch64|ppc64le|s390x) dir=linux-${1};;
    esac
    cp ./LICENSE ${OUTDIR}/${dir}
    tar --owner 0 --group 0 -C ${OUTDIR}/${dir} . -zcf ./tkn-${dir}-amd64-${TKN_VERSION}.tar.gz
}


pushd ${OUTDIR}
mkdir linux macos windows
wget "${TKN_URL}/signed/linux/tkn-linux-amd64" -O linux/tkn
wget "${TKN_URL}/signed/macos/tkn-darwin-amd64" -O macos/tkn
wget "${TKN_URL}/signed/windows/tkn-windows-amd64.exe" -O windows/tkn.exe
wget https://raw.githubusercontent.com/openshift/tektoncd-cli/master/LICENSE

pkg_tar x86_64
pkg_tar macos
cp ./LICENSE ${OUTDIR}/windows/
zip --quiet --junk-path - ${OUTDIR}/windows/* > "${OUTDIR}/tkn-windows-amd64-${TKN_VERSION}.zip"

sha256sum tkn-* > sha256sum.txt
mkdir ${TKN_VERSION}
mv *.tar.gz *.zip sha256sum.txt ${TKN_VERSION}
ln -sf ${TKN_VERSION} latest

# sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${TKN_VERSION}" latest \
    use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/pipeline/

popd

# kick off mirror push for pipeline dir
ssh ${SSH_OPTS} << EOF
    timeout 15m /usr/local/bin/push.pub.sh openshift-v4/clients/pipeline -v \
    || timeout 5m /usr/local/bin/push.pub.sh openshift-v4/clients/pipeline -v \
    || timeout 5m /usr/local/bin/push.pub.sh openshift-v4/clients/pipeline -v
EOF
