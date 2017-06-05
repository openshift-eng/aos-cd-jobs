#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

jobs=( provision upgrade terminate )

pushd sjb
for job in "${jobs[@]}"; do
    jenkins-jobs test jobs/${job}-job.yml > generated/continuous-upgrade_${job}-job.xml
done
popd