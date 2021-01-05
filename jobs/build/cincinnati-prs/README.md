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
* `eus` PRs are accepted 48 hours after release when OTA team has had some time to look for upgrade edges
  that they might need to exclude.(starting from 4.6, we plan to gradually use eus instead of stable,and after 4.10
  stable plan to be discard)

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

