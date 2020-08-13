# Manage OLM operator manifests in appregistry format

## Purpose

This job builds and publishes operator manifest images from OLM operators.

This will likely only make sense once you are familiar with
[What ART needs to know about OLM operators and CSVs](https://mojo.redhat.com/docs/DOC-1203429)
The way that multiple releases are intermingled is truly convoluted, see especially
[The current process](https://mojo.redhat.com/docs/DOC-1203429#jive_content_id_The_current_process).

Operator manifests (which include the CSV that OLM uses to manage the operator) are extracted
from the operator images and built into operator-metadata images. Then they are published:

* dev: the metadata image NVR is submitted to OMPS which retrieves and publishes it in redhat-operators-art
* stage, prod: the metadata image is attached to an advisory where it can be pushed to stage/prod

## Timing

* dev: ocp4 and custom jobs run this automatically to publish manifests for any new OLM operator builds they may have created.
* stage: [release-artists do a stage run to hand off new images for QE to verify in a release.](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-stage-operator-metadata-containers)
* prod: [release-artists do a prod run for a verified release when we are CERTAIN it will ship next.](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-prod-operator-metadata-containers)

Stage and especially prod builds for different versions MUST be pushed (to
stage or prod, respectively) in the same order that they are built to avoid
premature or regressed metadata for other versions.

The first prod build in a release cycle should not be performed until at least
Friday before a release, in case we need to change the order of releases for
some reason (it has happened).

## Becoming obsolete

In 4.6 we plan to use an entirely new workflow for publishing operator
manifests. Once we have fully moved over to bundle builds for all versions, we
can decommission this job and have a celebration.

## Parameters

### Standard BUILD\_VERSION, MOCK, SUPPRESS\_EMAIL

See [Standard Parameters](/jobs/README.md#standard-parameters).

### IMAGES

[List](/jobs/README.md#list-parameters) of image dist-gits to limit selection.

By default all active images are searched for the
`com.redhat.delivery.appregistry` label that indicates an OLM operator. This is
rather slow and sometimes you are only interested in a subset.

Also in the case of a stage/prod build, the source for images is the extras
advisory; by design, if all known OLM operators are not present, an error is
raised to prevent accidentally not shipping operators. If this is in fact
intentional, you will need to re-run with a constrained list (which is given to
you in the error message).

### STREAM

The goal is to get metadata into an appregistry where OLM can read it.

* dev: these run continuously after images are built, and publish to
  appregistry redhat-operators-art.
* stage: these are intended for stage testing in an advisory which publishes
  them to appregistry redhat-operators-stage.
* prod: these are intended for production release in an advisory which
  publishes them to appregistry redhat-operators (public).

All versions of an operator share the same metadata containers. A single
metadata container publishes manifests for all versions at the time.  So for
each stream, only one build can be running at a time, and others are locked.

### OLM\_OPERATOR\_ADVISORIES

[List](/jobs/README.md#list-parameters) of advisories where OLM operators are
attached (usually just one, but sometimes operator builds are in a separate
RHSA).
* These source advisories are required for `stage` and `prod` STREAMs

These are advisory numbers like `57834`.

### METADATA\_ADVISORY

For `stage` and `prod` STREAMs, this provides the advisory to attach metadata
builds that are produced.

This is a metadata advisory number like `57835`.

### FORCE\_METADATA\_BUILD

Always attempt to build the operator metadata, even if there is no new manifest to include.

Most of the time, manifest updates are idempotent. If there is nothing new to
include, there is no real reason to rebuild an image, so it is skipped.

This option overrides that and builds metadata images for all operators
regardless. Most of the time, there is no reason to use this. The main reason
to use it would be to work around an error in our code.

### SKIP\_PUSH

(`dev` stream only) Do not push operator metadata to OMPS. This would mostly be
useful for testing builds and not wanting to wait on the OMPS push.

### MAIL\_LIST\_FAILURE

Failure Mailing List - who to email when the job fails.

## Known issues

### "operators not found" / "Advisories missing operators"

In stage/prod builds, the source for images is the extras advisory; by design,
if all known OLM operators are not present, an error is raised to prevent
accidentally not shipping operators. If this is in fact intentional, you will
need to re-run with a constrained list (which is given to you in the error
message).

### "Expecting value: line X column 1 (char 0)"

This is a very obscure error message that indicates one or more of the operator
metadata containers wasn't built successfully. Figure out which one(s) are
missing and why they failed.

### Timing out on dev pushes

The dev flow requires the Container Verification Pipeline (CVP) to run against
the metadata container.  The CVP runs asynchronously after the OSBS image build
and is sometimes backed up or otherwise broken.  After 2 hours, the job gives
up and fails whatever hasn't completed. This is not usually a problem that we
actually need to do anything about, since the next run will update it, and
anyway, this is only dev.

### Failures in the actual manifests

The CVP runs operator manifest CSVs through a validation tool called
"Greenwave" which flags certain problems in the manifests. If these are
failing, we need to notify the operator owners to fix their manifests.

### Oops, I ran a prod push out of order and need to back it out

Use this job to revert all operators affected (usually all) to the previous release.

1. Determine the extras advisory for the previous release for this minor version.
  * Look at e.g. https://errata.devel.redhat.com/package/show/elasticsearch-operator-container
2. Run this job with that advisory as the operator source.
3. Run this job again for the minor version you need to release first.
