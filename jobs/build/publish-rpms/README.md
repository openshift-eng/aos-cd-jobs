# Publish latest RHEL 7 worker RPMs to mirror

## Purpose

This job will publish the dependent RPMs to mirror location under https://mirror.openshift.com/pub/openshift-v4/dependencies/rpms/<4.y-beta>
So that we can test out pre-GA versions on RHEL 7 workers

## Timing

The [pull-payload](https://github.com/openshift/aos-cd-jobs/tree/master/scheduled-jobs/build/poll-payload) job will trigger this job when create a new release branch for x86.

## Parameters

### BUILD\_VERSION

The name of the latest pre release, for example "4.7".

## Known issues

None yet.
