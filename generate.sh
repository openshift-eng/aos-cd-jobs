#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

for spec in commands/*; do
	test_name="$( basename "${spec}" ".sh" )"
	./render.py test_case.xml "command=$( sed 's/\$/\\$/g' "${spec}" )" > "${OUTPUT_DIR:-generated}/${test_name}.xml"
done

for spec in children/*; do
	test_name="$( basename "${spec}" ".txt" )"
	./render.py test_suite.xml "child_jobs=$( cat "${spec}" )" > "${OUTPUT_DIR:-generated}/${test_name}.xml"
done