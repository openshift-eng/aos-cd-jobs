#!/bin/bash

main() {
  set -euxo pipefail
  # Command line arguments
  WORKSPACE="$1"
  STREAM="$2"
  MIRROR="$3"

  # Global variables
  OC_MIRROR_DIR="/srv/pub/openshift-v4/clients/$MIRROR/"
  export MOBY_DISABLE_PIGZ=true
  SSH_OPTS="-l jenkins_aos_cd_bot -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com"

  release_info="$(
    curl --fail --show-error --silent --location \
      -X GET -G "$(get_url "$STREAM")" "$(get_curl_arg "$STREAM")"
  )"

  PULL_SPEC="$(get_pull_spec)"
  VERSION="$(get_version)"

  OUTDIR="${WORKSPACE}/tools/$VERSION"

  exit_if_mirrored "${OC_MIRROR_DIR}${VERSION}"

  extract_release_info "$OUTDIR" "$PULL_SPEC"

  full_mirror_push
}

get_curl_arg() {
  local version major minor tmp stream
  stream="$1"

  [[ "$stream" =~ ^[0-9]+.[0-9]+-stable$ ]] || return
  tmp="${stream%-*}"
  major="${tmp%.*}"
  minor="${tmp/*.}"

  echo "--data-urlencode 'in=>$major.$minor.0-0 <$major.$((minor + 1)).0-0'"
}

get_url() {
  local major stream url
  stream="$1"

  if [[ "$stream" =~ ^[0-9]+.[0-9]+-stable$ ]]; then
    major="${stream%.*}"
    url="https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/$major-stable/latest"
  else
    url="https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/$stream/latest"
  fi

  echo "$url"
}

get_pull_spec() {
  local pullspec release_info
  release_info="$1"

  pull_spec="$(jq -r '.pullSpec' <<<"$release_info")"
  if [[ "$MIRROR" == "ocp-dev-preview" ]]; then
    # point at the published pre-release that will stay around -- registry.svc.ci gets GCed
    pull_spec="${pull_spec/registry.svc.ci.openshift.org\/ocp\/release/quay.io/openshift-release-dev/ocp-release-nightly}"
  fi
  echo "$pull_spec"
}

get_version() {
  local release_info
  release_info="$1"
  echo "$(jq -r '.name' <<<"$release_info")"
}

exit_if_mirrored() {
  # check if already exists
  local dir
  dir="$1"
  if ssh ${SSH_OPTS} "[ -d '$dir' ]"; then
    echo "Already have latest version" >/dev/stderr
    exit 0
  fi
}

extract_release_info() {
  echo "Fetching OCP clients from payload ${VERSION}" >/dev/stderr

  local pullspec outdir
  pullspec="$1"
  outdir="$2"

  mkdir -p "$outdir"
  pushd "$pullspec"

  #extract all release assests
  GOTRACEBACK=all oc version
  GOTRACEBACK=all oc adm release extract --tools --command-os="*" "$pullspec" --to="$outdir"
  popd
}

sync_to_mirror() {
  # sync to use-mirror-upload
  pushd "$WORKSPACE/tools"
  rsync \
    -av --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX \
    -e "ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no" \
    "${OUTDIR}" \
    "use-mirror-upload.ops.rhcloud.com:${OC_MIRROR_DIR}"
  popd
}

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

full_mirror_push() {
  # kick off full mirror push
  retry ssh ${SSH_OPTS} timeout 15m /usr/local/bin/push.pub.sh openshift-v4 -v
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
