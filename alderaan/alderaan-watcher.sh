#!/bin/bash

jjb_config_path=$1
repo=$2
jobs_workdir=/root/aos-cd-jobs

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
