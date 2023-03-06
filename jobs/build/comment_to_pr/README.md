# Comment on a PR after a job

## Purpose
This job will be kicked off by ocp4 job (for now) after images are built. It will comment the nvr 
and the distgit details of that image to its source PR so that developers can know which build 
their PR ended up in, for a particular distgit.

## Parameters

### JOB_BASE_NAME

The name of the parent job that called this job. Eg: build/ocp4

### BUILD_NUMBER

The jenkins build number of the parent job.

So if the parent job that triggered this job is build/ocp4/4010, then JOB_BASE_NAME is build/ocp4
and the BUILD_NUMBER is 4010

### BUILD_NUMBER

The openshift release version, eg: 4.12

## Known issues

The job is checking for comments that are already posted to make sure that we are not 
spamming the PR, and it also checks for redundant PRs originating from cherry-picked commits
(mentioned in the appropriate section of the code). Hence no issues so far.