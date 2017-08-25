#!/bin/sh

pushd config > /dev/null
python ../graph.py > ../graph.dot
popd

fdp -Tpng graph.dot > graph.png
