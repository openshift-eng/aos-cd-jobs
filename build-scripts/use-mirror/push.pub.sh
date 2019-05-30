#!/bin/bash

set -e
set -o xtrace

timeout 30m /usr/local/bin/push.pub.sh "$@"

