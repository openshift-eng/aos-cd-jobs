#!/bin/bash

cd sjb
python -m generate config/test_cases/$TEST.yml "test" "sh"
chmod +x ./generated/${TEST}.sh
./generated/${TEST}.sh
