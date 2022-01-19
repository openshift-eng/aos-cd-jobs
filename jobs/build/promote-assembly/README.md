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

The job may fail if verification fails. It sends
slack alerts in a relevant release channel (like `art-release-4-7`) when this occurs.
You may rerun this job after the related issues are resolved.

## Timing

This job is run manually per the release schedule.

Promotion should wait for QE to have a chance to review, and should not occur
if there are blockers outstanding for a release. It may be delayed or omitted
as needed. In general, it is best if it occurs early in the day as the
acceptance tests are more likely to pass then.

## Parameters

### Standard parameters DRY\_RUN, MOCK

See [Standard Parameters](/jobs/README.md#standard-parameters).

### VERSION
This specifies the OCP minor version (e.g. 4.10)

### ASSEMBLY

This specifies the name of the assembly. The assembly must be explicitly defined in releases.yml.

### ARCHES

Leave this to empty to promote all supported architectures.
Otherwise, specify a list of architectures (separated by comma) to promote (e.g. x86_64,aarch64).

### RELEASE\_OFFSET

This parameter is required to promote a custom release. If offset is X for 4.9, the release name will be 4.9.X-assembly.ASSEMBLY_NAME.


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

### SKIP\_CINCINNATI\_PR\_CREATION

**DO NOT USE** without discussing with your team or pillar lead for approval.

This *prevents* creating PRs to enter the new release in Cincinnati (to make it
visible to customers for install/upgrade).

### SKIP\_OTA\_SLACK\_NOTIFICATION

Do not notify the OTA team in slack about new PRs created for Cincinnati.
Probably only useful for testing the job.

### SKIP\_IMAGE\_LIST

For a Standard `x86_64` release, this job normally gathers a list of images
from the image advisory and sends it to docs for inclusion in the release notes.

This option prevents that. There is probably not much reason to do this.

### MAIL\_LIST\_SUCCESS

Address(es) to mail when the job succeeds.

## Related Group config fields

The following fields can be defined in `group.yml` or `releases.yml` `assembly.group` section:

```yaml
advisories:
  image: 86637
  rpm: 86633
  extras: 86638
  metadata: 86639
upgrades: 4.6.24,4.6.25,4.6.26
description: "some text"
```

### upgrades

This is used to specify which releases to allow to upgrade to this release. This field is optional for custom releases.
If no upgrade edges are expected, please explicitly set the `upgrade` field to empty string.

### description

Should not be defined unless you know otherwise. This adds text in the release image
metadata that we have never actually had a use for. It has been available since
the beginning of OCP 4 and remains available in case we ever find a use for it.

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
