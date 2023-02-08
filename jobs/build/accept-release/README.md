# Accept a Named Release on Release controller

## Purpose

This job can be used to Accept/Reject a release/nightly on [release controller](https://amd64.ocp.releases.ci.openshift.org/).

## Timing

Sometimes we want to "Accept" currently "Rejected" nightlies when blocking tests are determined to be flaky. Sometimes we want to "Reject" long pending nightlies, to make way for newer nightlies.

After the [promote-assembly](https://github.com/openshift/aos-cd-jobs/tree/master/scheduled-jobs/build/promote-assembly) job creates a named release on Release controller, and it is "Rejected" due to failing tests, but newer tests pass - in which case we want to Accept it. 

## Parameters

### RELEASE_NAME
Release name (e.g 4.10.4) or nightly (4.10.0-0.nightly-2023-02-08-204248)

### ARCH
Release architecture (amd64, s390x, ppc64le, arm64)

### REJECT

Running without this would be an "Accept" action. Running with this would be a "Reject" action.
Default value is False.

### CONFIRM

Running without this would be a [dry-run]. Must be specified to apply changes to server
It's default value is False.

## Known issues

None yet.