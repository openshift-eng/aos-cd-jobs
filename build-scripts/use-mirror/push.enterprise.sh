#!/bin/bash

set -e
set -o xtrace

timeout 2h /usr/local/bin/push.enterprise.sh reposync -v

