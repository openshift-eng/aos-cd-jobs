#!/usr/bin/env bash

set -uo pipefail

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
  if [[ "$rpm" == *el9* ]]; then
    rpm2cpio "${rpm}" | zstd -d | cpio -idm --quiet ./usr/bin/coreos-installer
  else
    rpm2cpio "${rpm}" | cpio -idm --quiet ./usr/bin/coreos-installer
  fi
  mv usr/bin/coreos-installer "$VERSION/coreos-installer_$arch"
done

if [[ -f ${VERSION}/coreos-installer_amd64 ]]; then
    ln --symbolic --force --no-dereference coreos-installer_amd64 "${VERSION}/coreos-installer"
fi

tree "$VERSION"
