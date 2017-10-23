#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

pushd sjb >/dev/null

for file in $(python -m find_abandoned_xmls); do
	echo "Removing $file"
	rm $file
done

popd >/dev/null
