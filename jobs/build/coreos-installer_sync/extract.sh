#!/usr/bin/env bash

set -euo pipefail

WORKDIR="$1"
cd "$WORKDIR"
VERSION="$2"
ARCHES=""
if [[ -n "${3-}" ]]; then
  ARCHES="${3//,/ }"
  rm -rf keep/
  mkdir keep/
  for arch in $ARCHES; do
    case "$arch" in
      amd64) arch=x86_64 ;;
      arm64) arch=aarch64 ;;
    esac
    mv *.$arch.rpm keep/
  done
  rm *.rpm
  mv keep/* .
  rmdir keep/
fi

rm -rf "$VERSION"
mkdir "$VERSION"

for rpm in *.rpm; do
  arch="$(awk -F'[.]' '{a = $(NF-1); print a=="x86_64" ? "amd64" : a=="aarch64" ? "arm64" : a}' <<<"$rpm")"
  rpm2cpio "${rpm}" | cpio -idm --quiet ./usr/bin/coreos-installer
  mv usr/bin/coreos-installer "$VERSION/coreos-installer_$arch"
done

tree "$VERSION"
