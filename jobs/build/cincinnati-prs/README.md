# Create PRs for Cincinnati graph data

## Purpose

This performs a standard part of release management, as described in
https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#stage-the-release-candidate

This creates PRs to enter the new release in all the relevant Cincinnati channels.
(updates https://github.com/openshift/cincinnati-graph-data/tree/master/channels)

* `Candidate` PRs will be accepted immediately (in fact we plan to begin merging directly soon).

Subsequent promotion is managed by [the stabilization robot][stabilization-changes].

## Timing

The `promote` job runs this after the new release passes tests to be accepted.
A human would only need to run it if the job failed somehow before running it.

## Parameters

### Standard parameters MOCK

See [Standard Parameters](/jobs/README.md#standard-parameters).

### FROM\_RELEASE\_TAG

Nightly from which the release was derived. Only used for informational purposes on the Slack notification message.

### RELEASE\_NAME

The name of the release to add to Cincinnati via PRs, for example "4.5.6" or "4.6.0-fc.0"

### ADVISORY\_NUM

Internal advisory number for release;
The `56698` in https://errata.devel.redhat.com/advisory/56698

This is added to the PRs to help inform OTA team when they should merge.

### GITHUB\_ORG

The github org containing cincinnati-graph-data fork to open PRs against.
When testing this job, you can direct this to create PRs against your own fork
of the repo to avoid cluttering up the real repo. However openshift-bot may
not have permission to make PRs in your fork.

### SKIP\_OTA\_SLACK\_NOTIFICATION

Do not notify OTA team - normally when PRs are created we also send a slack notification
in `#forum-release`. You probably would want to set this while testing job changes.

## Known issues

None yet.

[stabilization-changes]: https://github.com/openshift/cincinnati-graph-data/blob/master/hack/stabilization-changes.py
