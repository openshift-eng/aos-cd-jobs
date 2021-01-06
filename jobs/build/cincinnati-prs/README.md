# Create PRs for Cincinnati graph data

## Purpose

This performs a standard part of release management, as described in
https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#stage-the-release-candidate

This creates PRs to enter the new release in all the relevant Cincinnati channels.
(updates https://github.com/openshift/cincinnati-graph-data/tree/master/channels)

* `Candidate` PRs will be accepted immediately (in fact we plan to begin merging directly soon).
* `Fast` PRs are accepted when the release ships to make it available for customers (intended for test/stage)
* `Stable` PRs are accepted 48 hours after release when OTA team has had some time to look for upgrade edges
  that they might need to exclude.
* `EUS` PRs are [created only for EUS releases](https://docs.google.com/document/d/1O_hv83qX2eHi82YOL75mWOizcrPI8xEgh6HEyLdBcpE/edit) (4.6, 4.10 planned) and like `Stable` are accepted 48 hours after release. While standard support is in place, both `eus` and `stable` channels will be updated in parallel; once standard support is complete and the release enters the EUS support phase, only the `eus` channel will be updated.

## Timing

The `promote` job runs this after the new release passes tests to be accepted.
A human would only need to run it if the job failed somehow before running it.

## Parameters

### Standard parameters MOCK

See [Standard Parameters](/jobs/README.md#standard-parameters).

### RELEASE\_NAME

The name of the release to add to Cincinnati via PRs, for example "4.5.6" or "4.6.0-fc.0"

### ADVISORY\_NUM

Internal advisory number for release;
The `56698` in https://errata.devel.redhat.com/advisory/56698

This is added to the PRs to help inform OTA team when they should merge.

### CANDIDATE\_CHANNEL\_ONLY

Only open a PR for the candidate channel - this would be for Feature Candidates or anything
else we never wanted to get into a supported channel.

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

