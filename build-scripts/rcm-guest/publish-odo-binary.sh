#!/bin/bash
set -euxo pipefail

GITHUB_TOKEN="$1"
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo Expecting an argument that will be used as the GitHub token. Exiting.>/dev/stderr
  exit 2
fi

SSH_OPTS="-n -l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

TMPDIR=$(mktemp -dt odobinary.XXXXXXXXXX)
trap "rm -rf '${TMPDIR}'" EXIT INT TERM
cd "${TMPDIR}"

# get latest release from GitHub API
curl -sSL -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/openshift/odo/releases/latest > latest
#extract tag version
VERSION=`jq -r '.tag_name' latest`
#extract download list
DOWNLOADS=`jq -r '.assets | .[] | .browser_download_url' latest`

#check if already exists
if ssh ${SSH_OPTS} "[ -d /srv/pub/openshift-v4/clients/odo/${VERSION} ]";
then
    echo "Already have latest version"
    exit 0
else
    echo "Fetching ODO client ${VERSION}"
fi


OUTDIR=${TMPDIR}/${VERSION}
mkdir "${OUTDIR}"
pushd ${OUTDIR}

#download all release assests
echo $DOWNLOADS | xargs wget
popd

# create latest symlink
ln -sf ${VERSION} latest

#sync to use-mirror-upload
rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${OUTDIR}" latest \
    use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/odo/


retry() {
  local count exit_code
  count=0
  until "$@"; do
    exit_code="$?"
    count=$((count + 1))
    if [[ $count -lt 4 ]]; then
      sleep 5
    else
      return "$exit_code"
    fi
  done
}

# kick off mirror push
retry ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4/clients/odo -v
