# Accept an OKD Release on Release Controller

## Purpose

This job can be used to Accept/Reject an OKD release/nightly on [release controller](https://amd64.ocp.releases.ci.openshift.org/).

Unlike the `accept-release` job, this job targets the `origin` namespace where OKD releases are stored.

## Parameters

### RELEASE_NAME

OKD release name (e.g. `5.0.0-0.okd-scos-nightly-2026-09-22-052225`).

### ARCH

Release architecture (amd64, s390x, ppc64le, arm64, multi). The release tool requires this option, although OKD releases use the `origin` namespace for all architectures.

### REJECT

Running without this performs an Accept action. Running with this performs a Reject action.

### JIRA_TICKET

The Jira ticket associated with the action (e.g. `ART-1234`).

### CONFIRM

Running without this performs a dry run. It must be specified to apply changes to the server.
