#!/bin/bash

set -o errexit   # All non-zero statuses will terminate script
set -o pipefail  # All components of piped command will terminate script if they fail
set -o nounset   # Makes substituting unset variables an error

opts="$( getopt -o hm:n: --long help,major:,minor: -n 'merge-and-build' -- "$@" )"
eval set -- "$opts"
major=""
minor=""
rcm_username="ose-cd-jenkins"
help=0

function usage() {
    echo "Syntax: --major=X --minor=Y"
}

# The use of `getopt` is considered less than desirable often, but is the only
# way to get double-dash long-form options. See also:
#
# Unless it's the version from util-linux, and you use its advanced mode, never
# use getopt(1). Traditional versions of getopt cannot handle empty argument
# strings, or arguments with embedded whitespace. The POSIX shell (and others)
# offer getopts which is safe to use instead.
# http://mywiki.wooledge.org/BashFAQ/035#getopts
while true; do
  case "$1" in
    -h | --help )
        help=1; shift
        ;;
    -m | --major )
        major="$2"; shift; shift
        ;;
    -n | --minor )
        minor="$2"; shift; shift
        ;;
    -- )
        shift; break
        ;;
    * )
        break
        ;;
  esac
done


if [[ "${help}" == "1" ]]; then
    usage
    exit 0
fi

if [[ -z "${major}" || -z "${minor}" ]]; then
    echo >&2 "--major and --minor are required"
    usage >&2
    exit 1
fi

set -o xtrace  # Verbose script execution output
ose_version="${major}.${minor}"

GOPATH=${HOME}/go
export GOPATH
workpath=${GOPATH}/src/github.com/openshift/
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
git remote add upstream git@github.com:openshift/origin.git
git fetch upstream master
git merge -m "Merge remote-tracking branch upstream/master" upstream/master
# Pull in the origin-web-console stuff
vc_commit=$(GIT_REF=master hack/vendor-console.sh | awk '/Vendoring origin-web-console/{print $4}')
git add pkg/assets/bindata.go
git add pkg/assets/java/bindata.go
git commit -m "Merge remote-tracking branch upstream/master, bump origin-web-console ${vc_commit}"

# Future - build a test rpm locally in mock?

# Have bew build the RPMs
tito tag --accept-auto-changelog
VERSION="v$(grep Version: origin.spec | awk '{print $2}')"; export VERSION
echo "${VERSION}"
git push

## Need kerberos credential
kinit -k -t $KEYTAB $PRINCIPLE
task_number="$( tito release --yes --test "aos-${ose_version}" | grep 'Created task:' | awk '{print $3}' )"
brew watch-task "${task_number}"

# RPMs are now built, on to the images
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf -n -s --label=building"
ose_images.sh update_docker --branch "rhaos-${ose_version}-rhel-7" --group base --force --release 1 --version "${VERSION}"
ose_images.sh build_container --branch "rhaos-${ose_version}-rhel-7" --group base --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo
sudo ose_images.sh push_images --branch "rhaos-${ose_version}-rhel-7" --group base   # Requires docker permissions
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/atomic_openshift-${ose_version}.conf"
# Script needs access to vagrant key
ssh "${rcm_username}@rcm-guest.app.eng.bos.redhat.com" "/mnt/rcm-guest/puddles/RHAOS/scripts/push-to-mirrors.sh simple ${ose_version}"

