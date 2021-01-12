#!/bin/bash

set -euo pipefail

TAG="${TAG:-${1:-}}"

if [[ -z "$TAG" ]]; then
    echo "Run only after running findit.sh and inspecting the unused-components file."
    echo "Specify the same tag to remove unused components from e.g.:"
    echo "  $0 rhaos-4.2-rhel-7-candidate"
    exit 1
fi

for pkg in $(cat unused-components); do
  echo "untagging all builds of $pkg from $TAG"
  brew untag-build "$TAG" $(brew list-tagged "$TAG" $pkg --quiet | awk '{ print $1 }')
done
