#!/bin/bash
set -euxo pipefail

SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"
KN_VERSION=${1:-0.2.3}
KN_URL=${2:-http://download.eng.bos.redhat.com/brewroot/vol/rhel-8/packages/openshift-serverless-clients/0.2.3/1.el8/data/signed/fd431d51/x86_64/openshift-serverless-clients-redistributable-0.2.3-1.el8.x86_64.rpm}

# check if already exists
### TODO: figure out why the script exits regardless of test result when this is uncommented:
#if ssh ${SSH_OPTS} "[ -d /srv/pub/openshift-v4/clients/serverless/${KN_VERSION} ]"
#then
#    echo "Already have latest version"
#    exit 0
#fi
echo "Fetching Knative client ${KN_VERSION}"

OUTDIR=$(mktemp -dt knbinary.XXXXXXXXXX)
trap "rm -rf '${OUTDIR}'" EXIT INT TERM

pkg_tar() {
    local dir
    case "$1" in
        x86_64) dir=linux;;
        macos) dir=macos;;
        aarch64|ppc64le|s390x) dir=linux-${1};;
    esac
    mkdir "${OUTDIR}/${dir}"
    mv ./usr/share/openshift-serverless-clients-redistributable/${dir}/kn-* ${OUTDIR}/${dir}/kn
    cp ./usr/share/licenses/openshift-serverless-clients-redistributable/LICENSE ${OUTDIR}/${dir}
    tar --owner 0 --group 0 -C ${OUTDIR}/${dir} . -zcf ./kn-${dir}-amd64-${KN_VERSION}.tar.gz
}

pushd ${OUTDIR}
wget "${KN_URL}"
rpm2cpio *.rpm | cpio -idmv --quiet
pkg_tar x86_64
pkg_tar macos
mkdir "${OUTDIR}/windows"
mv ./usr/share/openshift-serverless-clients-redistributable/windows/kn-windows-amd64.exe ${OUTDIR}/windows/kn.exe
cp ./usr/share/licenses/openshift-serverless-clients-redistributable/LICENSE ${OUTDIR}/windows/
zip --quiet --junk-path - ${OUTDIR}/windows/* > "${OUTDIR}/kn-windows-amd64-${KN_VERSION}.zip"

mkdir ${KN_VERSION}
mv *.tar.gz *.zip ${KN_VERSION}
ln -sf ${KN_VERSION} latest

# sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${KN_VERSION}" latest \
    use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/serverless/

popd

# kick off mirror push for serverless dir
ssh ${SSH_OPTS} << EOF
    timeout 15m /usr/local/bin/push.pub.sh openshift-v4/clients/serverless -v \
    || timeout 5m /usr/local/bin/push.pub.sh openshift-v4/clients/serverless -v \
    || timeout 5m /usr/local/bin/push.pub.sh openshift-v4/clients/serverless -v
EOF
