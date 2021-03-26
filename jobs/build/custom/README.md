# Run component builds in ways other jobs can't

## Purpose

This job is mainly used when you need to build something specific not handled
well by the `ocp3` or `ocp4` jobs and don't want to set up and use doozer.

It is also still necessary for building OCP 3.11 releases using signed RPMs in containers.

> :information_source: For 4.x this also follows up with operator metadata
> builds and build-sync, like the `ocp4` job.

> :information_source: Note that unlike the `ocp4` job, this job halts if there
> are build failures, so such failures are harder to miss.

## Timing

This is only ever run by humans, as needed. No job should be calling it.

## Parameters

### Standard parameters BUILD\_VERSION, MOCK, SUPPRESS\_EMAIL

See [Standard Parameters](/jobs/README.md#standard-parameters).

### IGNORE\_LOCKS

By default build jobs use locks to prevent conflicting updates to the same
version, so this job may wait on another long-running incremental build. If you
know your build will not conflict with other builds (doesn't use the same
dist-gits or it just doesn't matter that much) then you can use this option to
ignore other locks and go ahead with your build.

This is useful for instance when you are working on a new image that isn't even
enabled yet and nothing else is building it.

Note that compose locks are still respected, since those are not specific to individual builds.

### VERSION

(Optional, not usually needed.)
This is the `version` (e.g. `4.3.42`) part of the component build
`name-version-release` (NVR) and works just like in the `ocp4` job. RPM builds
use the exact version and container image builds prefix it with `v`. Either
format may be specified.

The default is to use the latest version of the `atomic-openshift` package (in
3.11) or `openshift` package (in 4.y) tagged in brew with the minor version
tag.

You can specify an explicit version. You can put `+` to bump the most recent
version by one. After 4.3 the version is pegged to `4.y.0` so there's really no
point at all in setting this field. Either the job or doozer will raise an
error if you set an invalid version.

### RELEASE

(Optional, not usually needed.)
This is the `release` (e.g. `202008131234`) part of the component build `name-version-release` (NVR).

The default is `1` for 3.11. If the version you are (re)building already has
images, you should bump this to a later `release` than has been used for this
version. For example if the ocp3 job built `v3.11.150-1` then you would specify
`2` here to avoid reusing the same NVRs.

The default is `<timestamp>.p?` for 4.y builds. There's rarely any reason to
specify something different (but it would still need to end in `.p?`).

### DOOZER\_DATA\_PATH

This is possibly the most useful parameter for this job. It specifies the fork
of [ocp-build-data](https://github.com/openshift/ocp-build-data) to be used as
configuration for this build.

Override this with your fork when you want to try out some configuration
without committing it to the canonical repo.  The same branching structure is
expected, so for instance if you are running a `4.6` build, it will be looking
at the `openshift-4.6` branch (there is no way to use an arbitrary feature
branch or tag).

You can use this, for example, to test building against a feature branch in a
source github repo before its PR merges.  Update the `ocp-build-data` metadata to
point at the source fork and branch; commit that change on the usual branch,
push it to your fork, and run this job against your fork.

> :warning: Keep in mind that this does not _merge_ the source github feature
> branch... it uses exactly what is there.

> :warning: Also keep in mind that this build will be tagged and synced like
> any other build - usually it should be followed up with a proper build once
> the source PR has merged (or been abandoned). In practice, incremental builds
> will usually take care of this if allowed to run.

### RPMS

[List](/jobs/README.md#list-parameters) of package dist-gits to build.  Leave
this empty to build all that are active. Enter `NONE` to prevent building any.

Because `custom` is most commonly used only to build images, the default value
here is `NONE`.

### COMPOSE

The purpose of this parameter is to ensure images build with the latest
available RPMs, including those being built in this job; but not to waste time
creating new composes if there are no changes.

If true, new plashets (in 4.y) or a new unsigned compose (in 3.11) will be
built in between building RPMs (if any) and images (if any).

If this run is building RPMs, this parameter is ignored and new
plashets/compose are always built to include them.

A slack notification is sent to the respective release channel in either case,
that is if this parameter is set true or if this run is building RPMs.

### IMAGES

[List](/jobs/README.md#list-parameters) of image dist-gits to build.  Leave
this empty to build all that are active. Enter `NONE` to prevent building any.

### EXCLUDE\_IMAGES

[List](/jobs/README.md#list-parameters) of image dist-gits to SKIP building -
if specified, all _other_ active images are built (the `IMAGES` value is
ignored if this parameter is specified).

This works like `BUILD_IMAGES: except` in the `ocp4` job; in fact `custom`
should change to using the same parameters at some point, just for consistency.

### IMAGE\_MODE

This specifies the mode to use with doozer to update image dist-gits:
* `rebase`: this default is almost always what you should use. It rebases the
  code in the dist-git with the current source code.
* `update-dockerfile`: just update the Dockerfile with new metadata, not new
  source. This is useful for rebuilding 3.11 images with signed RPMs without
  changing source contents at all, but in 4.y should almost never be used
  (see below).
* `nothing`: change nothing, just build with current dist-git contents. This will
  not work as desired if the contents have already built successfully. This is
  only useful to retry a build that failed for some reason - bugs, system
  failures, buildroot changes, and such. There is not usually much need for this
  option.

> :warning: In 4.y, when rebuilding an OLM operator or operand, a rebase is
> required in order for the operator CSV references to work correctly
> (otherwise they are likely to point at images that are not published). Other
> images can be built with `update-dockerfile` safely in the case where you
> don't want to pull in newer changes; but this is a rare use case, and you
> don't want to get sloppy and include an operator/operand by accident.

### SCRATCH

Build "scratch" brew builds; code is pushed to dist-git and built in brew but
the builds do not get an NVR, can't be tagged, and can't interfere with
shipping builds. This is intended to be using only for testing builds.

:warning: Nothing can build on a scratch build (there is no registry tag), so
scratch builds of a parent and descendant are not possible. The descendant
build will fail. This can only be used for targeted builds, not a mass rebuild.
:warning:

After a scratch build, images will not be synced.

### SWEEP\_BUGS

When true, run the `sweep` job to sweep and attach `MODIFIED` bugs into the
default advisories for the build version (_NOT_ those specified by parameters
below).

> :warning: Note that this sweeps _all_ bugs, regardless of whether any builds
> include related changes. Usually this is not desired, but may be useful if
> you know all bugs will be ready to be swept at the end of the build.

### IMAGE\_ADVISORY\_ID

(Optional) If specified, attach _all_ latest container images to this advisory
when the job completes. Specify `default` to use the default value from
`ocp-build-data`.

In 3.11 this can be useful when doing the signed build for a release, to sweep
all the containers images when built.

In 4.y builds there is little use for this. It is not scoped to just the images
that were built in this run - it will attempt to attach _all_ latest images to
a single advisory (not split by payload/extras). This is basically only useful
for looking at CHI grades before continuing.

> :warning: This attempts to attach all builds to the same advisory, but if
> builds are already attached elsewhere, they will not be re-attached.

### RPM\_ADVISORY\_ID

(Optional) If specified, attach _all_ latest RPM package builds to this
advisory when the job completes. Specify `default` to use the default value
from `ocp-build-data`.

There is little use for this.
* In 3.11 you will usually want to sweep RPMs with the `signed-compose` job.
* In 4.y RPM builds have usually already been swept, but you may want to use this
  if the job built new ones.

> :warning: This attempts to attach all builds to the same advisory, but if
> builds are already attached elsewhere, they will not be re-attached.

### MAIL\_LIST\_SUCCESS

(Optional) Comma-separated list of addresses to email when this job completes successfully.

### MAIL\_LIST\_FAILURE

(Optional) Comma-separated list of addresses to email when this job fails to complete.

> :information_source: Note that unlike the `ocp4` job, this job halts if there
> are build failures, so such failures are harder to miss.

## Known issues

### Bug and build sweeps often do not work intuitively

Read carefully the explanations for what related parameters do before using them.

### 3.11 rebuilds require updating `RELEASE`

See the explanation of this parameter; rebuilds usually require bumping to `2` or higher.


