#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace
latest=$( readlink $HOME/origin-ci-tool/latest )
touch $latest
cp $latest/bin/activate $WORKSPACE/activate
cat >> $WORKSPACE/activate <<EOF
export OCT_CONFIG_HOME=~/continuous-upgrade/
EOF

source $WORKSPACE/activate
oct deprovision