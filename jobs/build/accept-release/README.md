# Accept/Reject a Release on Release Controller

## Purpose

This job can be used to Accept or Reject an OCP or OKD release/nightly on [release controller](https://amd64.ocp.releases.ci.openshift.org/). It supports both products through a single unified Jenkins job.

## Timing

Sometimes we want to "Accept" currently "Rejected" nightlies when blocking tests are determined to be flaky. Sometimes we want to "Reject" long pending nightlies, to make way for newer nightlies.

After the [promote-assembly](https://github.com/openshift-eng/aos-cd-jobs/tree/master/scheduled-jobs/build/promote-assembly) job creates a named release on Release controller, and it is "Rejected" due to failing tests, but newer tests pass - in which case we want to Accept it.

## Parameters

### PRODUCT
Which product the release belongs to. Choice of `ocp` (default) or `okd`. When set to `okd`, the job passes `--name okd` to target the OKD namespace on the release controller.

### RELEASE_NAME
The release or nightly name to accept/reject.

- OCP examples: `4.10.4` (named release) or `4.10.0-0.nightly-2023-02-08-204248` (nightly)
- OKD examples: `5.0.0-0.okd-scos-nightly-2026-09-22-052225`

### ARCH
Release architecture. One of: `amd64`, `s390x`, `ppc64le`, `arm64`, `multi`. Defaults to `amd64`.

### REJECT
When `false` (default), the action is "Accept". When `true`, the action is "Reject".

### JIRA_TICKET
The Jira ticket associated with this action (e.g. `ART-1234`). This is included in the message recorded on the release controller.

### CONFIRM
When `false` (default), the job runs as a dry-run. Must be set to `true` to apply changes to the server.

## Known issues

None yet.
