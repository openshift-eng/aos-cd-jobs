#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

for spec in sjb/config/test_cases/*.yml; do
	python -m sjb/generate "${spec}" "test"
done

for spec in sjb/config/test_suites/*.yml; do
	python -m sjb/generate "${spec}" "suite"
done