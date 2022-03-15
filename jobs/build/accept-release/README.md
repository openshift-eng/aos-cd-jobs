# Accept a Named Release on Release controller

## Purpose

This job can be used to "Accept" a previously "Failed" release on [release controller](https://amd64.ocp.releases.ci.openshift.org/) given a passing upgrade test url. Only intended/available for x64 arch for now.

## Timing

After the [promote-assembly](https://github.com/openshift/aos-cd-jobs/tree/master/scheduled-jobs/build/promote-assembly) job creates a named release on Release controller, and either the upgrade or upgrade-minor tests fail to turn the Release to "Failed" state.

## Parameters

### RELEASE_NAME
Release name (e.g 4.10.4). Arch (and release controller) is amd64 by default


### UPGRADE_URL
URL to successful upgrade job example: https://prow.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/575


### UPGRADE_MINOR_URL
URL to successful upgrade-minor job example: https://prow.ci.openshift.org/view/...origin-installer-e2e-gcp-upgrade/575


### CONFIRM

Running without this would be a [dry-run]. Must be specified to apply changes to server
It's default value is False.

### ALLOW_UPGRADE_TO_CHANGE

For allowing upgrade_to version change with new test. Use with caution
It's default value is False.

## Known issues

None yet.
