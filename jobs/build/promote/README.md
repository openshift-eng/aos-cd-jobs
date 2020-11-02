# Promote OCP 4 release images

## Purpose

This job creates release images as described in the
[4.y z-stream doc](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-the-release-image)
and publishes them to be available for customers.

The "release image" (also known as the "payload") represents the core OpenShift
artifacts. It is a container image built on the `cluster-version-operator`
member, adding references to all of the container images that are considered
part of core OpenShift. These references are pullspecs to where those images
can be found (by sha256sum) under the monorepo
quay.io/openshift-release-dev/ocp-v4.0-art-dev

Extras images (OLM operators/operands/bundles, miscellaneous tools) are not
part of the release image (though they are part of a release), and must be
published and pulled from registry.redhat.io instead of quay.io. Payload
and extras images are sorted into separate advisories for a release.

During development, architecture-specific release-controllers create "nightly"
(the name has stuck although they're created much more often) release images
for each architecture with all of the latest builds. When ART is preparing for
a release, we select a set of nightly images (one per arch) for QE to verify.
The purpose of this job is to re-build and publish a release image for customer
use after QE verification.

For the default use case, this job:
 * performs basic validation of the release contents
 * publishes a nightly as an [officially named release image](https://amd64.ocp.releases.ci.openshift.org/#4-stable) with with a list of releases allowed to upgrade to it
 * waits up to three hours for the release to pass acceptance tests (currently, just upgrade tests)
 * opens pull requests to [cinci-graph-data](https://github.com/openshift/cincinnati-graph-data/tree/master/channels)
 * copies the clients to the [mirror](http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/)
 * signs the clients and release image
 * ...and handles other odds and ends for a release

There are minor differences when this job runs for FCs, RCs, or hotfixes.

The job may pause for user input when needed or if verification fails. It sends
slack alerts in a relevant release channel (like `art-release-4-7`) when this occurs.

## Timing

This job is run manually per the release schedule. Currently it has to be run
separately per architecture, but we should wait for all architectures to be
ready before beginning any.

Promotion should wait for QE to have a chance to review, and should not occur
if there are blockers outstanding for a release. It may be delayed or omitted
as needed. In general, it is best if it occurs early in the day as the
acceptance tests are more likely to pass then.

## Parameters

### Standard parameters DRY\_RUN, MOCK

See [Standard Parameters](/jobs/README.md#standard-parameters).

### FROM\_RELEASE\_TAG

The existing release tag to pull from (e.g. 4.6.0-0.nightly-s390x-2020-11-06-181325).
This should be listed as `Accepted` in one of the release-controllers: \[
  [x86\_64](https://amd64.ocp.releases.ci.openshift.org/) |
  [s390x](https://s390x.ocp.releases.ci.openshift.org/) |
  [ppc64le](https://ppc64le.ocp.releases.ci.openshift.org/)
  \]

Normally a release ARTist will be promoting a nightly, but it is also possible
to re-promote an RC build to a GA release.

### RELEASE\_TYPE

This specifies what type of release to publish for customer use. Releases may be:

* **named** (given a different name from their source release image)
* Built with **signed** RPMs
* Upgrade targets (by specifying **previous** releases that can upgrade to them)
* Destined for various Cincinnati **channels**

The types are:

**1. Standard Release (Named, Signed, Previous, All Channels)**

This is what we use the job for most of the time - GA and z-stream releases.

**2. Release Candidate (Named, Signed, Previous, Candidate Channel)**

Release candidates are intended to be actual candidates for being released
as-is at a minor version GA. As such, they should have populated advisories
that are valid to ship. These are pretty much ART practice runs for the real
GA.

**3. Feature Candidate (Named, Signed - rpms may not be, Previous, Candidate Channel)**

Feature candidates enable customers/partners/developers to try out the features
coming in a new minor version, as well as upgrades. These are crucial to enable
the ecosystem to discover bugs as well.

FCs begin after feature freeze and continue regularly until we are ready for a
release candidate (hopefully, at code freeze). From ART's perspective they are
simply renamed nightlies and should not use signed RPMs or even have
advisories. However, these are entered in Cincinnati candidate channels to
enable exercising upgrades normally.

**4. Hotfix (No name, Signed, No Previous, All Channels)**

A hotfix is basically a nightly that gets added to Cincinnati channels. It is
used to solve an acute customer problem and intended only to be used until the
next z-stream release. It is added to channels only to enable the customer to
upgrade *away* from it in a supported fashion (they must do a "force" ugprade
*to* it in the first place).

### ARCH

This should nearly always be `auto` for promoting a nightly, since the nightly
name implies which architecture to use; but it is also possible to re-promote
an RC release to a GA release, and since an RC release has multiple
architectures, the `ARCH` parameter must be specified to distinguish which
architecture to promote.

### RELEASE\_OFFSET

Releases are distinguished from others in the same minor version only by an integer offset.
This offset (call it X) is used to construct the release name depending on the release type:

1. Standard Release: `4.y.X`
2. Release Candidate: `4.y.0-rc.X`
3. Feature Candidate: `4.y.0-fc.X`
4. Hotfix: do not specify an offset; the name of the nightly is re-used.

### DESCRIPTION

Should be empty unless you know otherwise. This adds text in the release image
metadata that we have never actually had a use for. It has been available since
the beginning of OCP 4 and remains available in case we ever find a use for it.

### ADVISORY

We need to know the advisory that will be used to ship the payload (AKA `image`
advisory in `group.yml`). We will link to its Live ID in the image metadata and
the release notes. We will also use it for release verification (that payload
images are attached, that bugs are valid, and whatever else we come up with).

**Most of the time you can leave this blank** and the `image` advisory from
`group.yml` will be used.

* For RC, GA and z-stream promotion normally this would be accurate.
* FCs and hotfixes don't use this at all.

For a `DRY_RUN` where you don't want advisory/release validation, you can put
`-1` here to skip it. There may be other edge cases where you want a manual
override.

Once we have `releases.yml` automation this should go away entirely in favor of
using the advisories from our configuration.

### PREVIOUS

This is used to specify which releases to allow to upgrade to this release.

If you leave it as `auto`, you will be prompted later in the job with suggested
previous releases.  Otherwise, follow
[item #6 "PREVIOUS" of the z-stream doc](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-the-release-image)
for instructions on how to fill this field.

Once we have `releases.yml` automation this should go away entirely in favor of
determining the releases from our configuration.

### PERMIT\_PAYLOAD\_OVERWRITE

**DO NOT USE** without discussing with your team or pillar lead for approval.

This allows the pipeline to overwrite an existing payload in quay. We have
done this a few times in the past and it has caused weirdness. Really, if a
release has been created and we can't use it, we should just create another.
Probably we should just get rid of this option.

### SKIP\_VERIFY\_BUGS

For a standard release, skip verifying advisory bugs.

You may want to use this to save time on releases with thousands of bugs that
have already been verified (say while releasing another arch).

### ENABLE\_AUTOMATION

"Yes" will update the `freeze_automation` entry in ocp-build-data to re-enable
automated incremental builds for this version.

**Default**: "Yes" for Standard and RC releases with arch `x86_64`, "No" otherwise.

Usually we want to do this to allow builds to begin after the release is
promoted; set to "No" only if you know of a reason why we want to keep the
version closed to further builds.

### SKIP\_CINCINNATI\_PR\_CREATION

**DO NOT USE** without discussing with your team or pillar lead for approval.

This *prevents* creating PRs to enter the new release in Cincinnati (to make it
visible to customers for install/upgrade).

### OPEN\_NON\_X86\_PR

Usually Cincinnati PRs will only be opened when `x86_64` releases are created.
If set, this will force their creation for any CPU arch.
There is no obvious use case for this.

### SKIP\_OTA\_SLACK\_NOTIFICATION

Do not notify the OTA team in slack about new PRs created for Cincinnati.
Probably only useful for testing the job.

### PERMIT\_ALL\_ADVISORY\_STATES

**DO NOT USE** without discussing with your team or pillar lead for approval.

There is a validation against the `image` advisory that is intended (among
other things) to guard against incidents where we accidentally pasted the wrong
release's advisory. Since those advisories would typically either be new or in
some stage of the shipping process, validation requires that the advisory be in
QE state for a Standard promotion.

This option allows Standard promotion when the image advisory is not in `QE`
state.  You might need this if advisories have already been changed to
`REL_PREP` - perhaps to promote a late re-spin. There are not many other
reasons to use this. Before you do, double-check the `image` advisory and
make sure it's the one you want.

### SKIP\_IMAGE\_LIST

For a Standard `x86_64` release, this job normally gathers a list of images
from the image advisory and sends it to docs for inclusion in the release notes.

This option prevents that. There is probably not much reason to do this.

### MAIL\_LIST\_SUCCESS

Address(es) to mail when the job succeeds.

### MAIL\_LIST\_FAILURE

Address(es) to mail when the job fails.

## Dependencies

Aside from all the jobs that had to run before this one in order to prepare release artifacts in the first place,
this job also relies on other jobs as part of its function.

### oc\_sync

Actually this job is _not_ invoked; but the code for syncing the oc client out
to mirror.openshift.com is shared between the jobs, which is useful when
something prevents completing the sync step during the promotion.

### signing-jobs/sign-artifacts

Once the release image is created (and if necessary has passed tests), the
[signing job](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/signing-jobs/job/signing%252Fsign-artifacts/)
is used to sign the release image and oc client with Red Hat's key.

### cincinnati-prs

After signing the release, the
[cincinnati-prs job](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/job/build%252Fcincinnati-prs/)
is used to create PRs to have the release (and upgrade edges) included in OCP 4
[release channels](https://github.com/openshift/cincinnati-graph-data/tree/master/channels).

## Known issues

### General flakiness

Considering the importance of this job, it is ironically difficult to change
and test safely. This is mainly because the job relies on making actual changes
(creating a release in `4-stable`, syncing clients) and then following up on
the results, and it's impossible to test all the logic even with a dry run.
And we only run it a few times a week.

So changes frequently break the job right when we need it and leave a release incomplete.

Most of what should have happened later in the job can be replicated by manually
running other jobs, which is useful when it breaks for some reason. See:
[Release job failures](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#release-job-failures)
