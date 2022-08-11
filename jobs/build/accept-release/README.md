# Accept a Named Release on Release controller

## Purpose

This job can be used to "Accept" a release on [release controller](https://amd64.ocp.releases.ci.openshift.org/). Only intended/available for x64 arch for now.

## Timing

After the [promote-assembly](https://github.com/openshift/aos-cd-jobs/tree/master/scheduled-jobs/build/promote-assembly) job creates a named release on Release controller, and either the upgrade or upgrade-minor tests fail to turn the Release to "Failed" state.

## Parameters

### RELEASE_NAME
Release name (e.g 4.10.4). Arch (and release controller) is amd64 by default


### CONFIRM

Running without this would be a [dry-run]. Must be specified to apply changes to server
It's default value is False.

## Known issues

None yet.
