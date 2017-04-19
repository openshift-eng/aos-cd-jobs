#!/bin/bash

set -o errexit
set -o nounset

for inputFile in ./testdata/*; do
	if [[ "$inputFile" =~ _input ]]; then
		tc="${inputFile%_input}"
		echo "Running test case ${tc#./testdata/}."
		scripts/rebase.py $inputFile
		outputFile="${inputFile%_input}_output"
		diff $inputFile $outputFile
	fi
done

echo "SUCCESS!"
