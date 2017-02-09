#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

export OUTPUT_DIR="${TMPDIR:-"/tmp"}/test-generate"
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"
./generate.sh
diff "${OUTPUT_DIR}" ./generated