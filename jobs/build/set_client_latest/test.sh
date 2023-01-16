#!/bin/bash
set -ex

RELEASE=4.13.0-ec.1
if [[ "$RELEASE" =~ -[ef]c\.[0-9]+ ]]; then
    CLIENT_TYPE="ocp-dev-preview"
else
    CLIENT_TYPE="ocp"
fi
