#!/bin/sh

set -o errexit   # All non-zero statuses will terminate script
set -o pipefail  # All components of piped command will terminate script if they fail

opts=`getopt -o hm:n: --long help,major:,minor: -n 'merge-and-build' -- "$@"`
eval set -- "$opts"
major=""
minor=""
rcm_username="ose-cd-jenkins"
help=0

function usage() {
    echo "Syntax: --major=X --minor=Y"
}

while true; do
  case "$1" in
    -h | --help )    help=1; shift ;;
    -m | --major ) major="$2"; shift; shift ;;
    -n | --minor ) minor="$2"; shift; shift ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done


if [[ "$help" == "1" ]]; then
    usage
    exit 1
fi

if [[ "$major" == "" || "$minor" == "" ]]; then
    echo "--major and --minor are required"
    usage
    exit 1
fi

set -o xtrace  # Verbose script execution output
ose_version="${major}.${minor}"

buildpath="~/go"
cd "$buildpath"
export GOPATH=`pwd`
workpath="${buildpath}/src/github.com/openshift/"
cd "${workpath}"

# Clean up old clones
rm -rf ose origin origin-web-console

# Setup origin-web-console stuff
git clone git@github.com:openshift/origin-web-console.git
cd origin-web-console/
git checkout "enterprise-${ose_version}"
git merge master -m "Merge master into enterprise-${ose_version}"

# Setup ose
cd "${workpath}"
git clone git@github.com:openshift/ose.git
cd ose
git add remote upstream git@github.com:openshift/origin.git
git fetch --all
git merge -m "Merge remote-tracking branch upstream/master" upstream/master
# Pull in the origin-web-console stuff
vc_commit="$(GIT_REF=master hack/vendor-console.sh 2>/dev/null | grep "Vendoring origin-web-console" | awk '{print $4}')"
git add pkg/assets/bindata.go
git add pkg/assets/java/bindata.go
git commit -m "Merge remote-tracking branch upstream/master, bump origin-web-console ${vc_commit}"

# Future - build a test rpm locally in mock?

# Have bew build the RPMs
tito tag --accept-auto-changelog
export VERSION="v$(grep Version: origin.spec | awk '{print $2}')"
echo ${VERSION}
git push
## Need kerberos credential      * How to initialize kerberos credential
# kinit ??
task_number=`tito release --yes --test aos-${ose_version} | grep 'Created task:' | awk '{print $3}'`
brew watch-task "${task_number}"

# RPMs are now built, on to the images
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf -n -s --label=building"
ose_images.sh update_docker --branch "rhaos-${ose_version}-rhel-7" --group base --force --release 1 --version "${VERSION}"
ose_images.sh build_container --branch "rhaos-${ose_version}-rhel-7" --group base --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo
sudo ose_images.sh push_images --branch "rhaos-${ose_version}-rhel-7" --group base   # Requires docker permissions
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf"
# Script needs access to vagrant key
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "/mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors.sh simple ${ose_version}"

