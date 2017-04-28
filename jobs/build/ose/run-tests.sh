#!/bin/bash

set -o errexit
set -o nounset

for inputFile in ./testdata/*; do
	if [[ "$inputFile" =~ _input ]]; then
		tc="${inputFile%_input}"
		echo "Running test case ${tc#./testdata/}."

		outputFile="${inputFile%_input}_output"
		if [[ ! $inputFile =~ broken ]]; then
			scripts/rebase.py $inputFile
		else
			set +e
			msg=$(scripts/rebase.py $inputFile 2>&1)
			if [[ "$?" == "0" ]]; then
				echo "Expected an error but got none!"
				exit 1
			fi
			echo $msg > $inputFile
			set -e
		fi

		diff $inputFile $outputFile
	fi
done

echo "SUCCESS!"
