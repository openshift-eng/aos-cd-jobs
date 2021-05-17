# Drop Advisories Job

## Description

Drop (mark as not shipping) one or more advisories in ErrataTool. Runs elliott command of the same name.

## Purpose

Sometimes we need to drop advisories, in cases like
- No updated builds found for shipping - in which case we don't need that advisory.
  - when no rpm builds are found, we drop rpm advisory
  - when no "extras" operator build found, then we drop extras and metadata advisories.
- Release as a whole is dropped due to some blocker.
- Duplicate advisories created by error (this has happened!)

Previously in case an ARTist wants to drop advisories, we would find somebody higher up to drop it, or manually run elliott from buildvm. This is a wrapper job that runs `elliott advisory-drop` with buildvm privileged credentials.

## Timing

When an ARTist realizes advisory(s) need to be dropped.

## Parameters

See [Standard Parameters](/jobs/README.md#standard-parameters).

### ADVISORIES

A list of one or more ErrataTool advisories numbers (e.g 66039), comma separated.
