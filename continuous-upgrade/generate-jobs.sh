#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

jobs=( provision upgrade terminate cicd-upgrade cicd-start-load cicd-dump-load-logs cicd-get-load-logs )

pushd continuous-upgrade
for job in "${jobs[@]}"; do
    jenkins-jobs test jobs/${job}-job.yml > generated/continuous-upgrade_${job}-job.xml
done
popd