#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace
echo $HOME
latest=$( readlink $HOME/origin-ci-tool/latest )
touch $latest
cp $latest/bin/activate $WORKSPACE/activate
cat >> $WORKSPACE/activate <<EOF
export OCT_CONFIG_HOME=$WORKSPACE/.config
EOF

source $WORKSPACE/activate
mkdir -p $OCT_CONFIG_HOME
rm -rf $OCT_CONFIG_HOME/origin-ci-tool
oct configure ansible-client verbosity 2
oct configure aws-client 'keypair_name' 'libra'
oct configure aws-client 'private_key_path' '/var/lib/jenkins/.ssh/devenv.pem'