#!/bin/bash

jjb_config_path=$1
repo=$2
jobs_workdir=/root/aos-cd-jobs
properties_workdir=/root/scale-ci-properties
properties_repo=https://github.com/redhat-performance/scale-ci-properties.git
jjb_output_path=$jobs_workdir/alderaan/jjb/dynamic
keys_path=/root/.ssh/authorized_keys

function usage() {
        echo "syntax: $0 <PATH TO THE CONFIG> [REPO]"
}

if [[ -z "$jjb_config_path" ]]; then
        usage
        exit 1
fi

if [[ -z "$repo" ]]; then
	repo=https://github.com/openshift/aos-cd-jobs.git
fi

# install jenkins job builder and dependencies if not already installed
which jenkins-jobs &>/dev/null
if [[ $? != 0 ]]; then
	echo "Looks like the jenkins-job-builder is not installed"
	echo "Installing Jenkins job builder"
	pip install jenkins-job-builder
	pip uninstall six -y
	pip install six
fi

# setup jjwrecker and convert xml to jjb
which jjwrecker &>/dev/null
if [[ $? != 0 ]]; then
        echo "Looks like the jjwrecker is not installed"
        echo "Installing"
        pip install jenkins-job-wrecker
fi
pushd $jobs_workdir/alderaan/xml
for xml_template in $(ls $jobs_workdir/alderaan/xml); do
	jjb_filename=$(basename $xml_template | cut -d '.' -f1)
	jjwrecker -f $xml_template -n $jjb_filename -o $jjb_output_path
	if [[ $? != 0 ]]; then
		echo "Failed to convert xml to jjb template, please check"
		exit 1
	fi
done
popd

# create jobs in openshift-qe jenkins
if [[ ! -d "$jobs_workdir" ]]; then
	git clone $repo $jobs_workdir
fi
pushd $jobs_workdir/alderaan/jjb/dynamic
for template in $(ls $jobs_workdir/alderaan/jjb/dynamic); do
	jenkins-jobs --conf "$jjb_config_path" update "$template"
	if [[ $? != 0 ]]; then
		echo "Failed to create the jenkins job, please check"
		exit 1
	fi
done
popd

# allow users to access the cluster
git clone $properties_repo $properties_workdir
pushd $properties_workdir
for key in $(ls public_keys); do 
	cat $key >> $keys_path
done
popd
