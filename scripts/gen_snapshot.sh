#!/usr/bin/env bash

echo "INSTALLED PYTHON PACKAGES"
echo "========================="
pip3 freeze

echo ""
echo "INSTALLED YUM PACKAGES"
echo "======================"
yum list installed

echo ""
echo "MOUNT INFO"
echo "==========="
mount