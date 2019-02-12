#!/bin/bash

set -e
set -o xtrace

timeout 1h /usr/local/bin/push.enterprise.sh all -v

