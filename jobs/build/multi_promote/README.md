# Multi Promote Job

## Description

Promote multiple nightlies as release payloads. Supports different release types.

## Purpose

This is a wrapper job for triggering multiple Promote jobs, for each architecture
to create release payloads for a single release. 

See [Promote job Readme](../promote/README.md) as the canonical source and documentation
for what Promote job does.

## Timing

This job is run manually per the release schedule. It requires nightlies for
all arches to be ready, to be given as input. 

Promotion should wait for QE to have a chance to review, and should not occur
if there are blockers outstanding for a release.

## Parameters

See [Standard Parameters](/jobs/README.md#standard-parameters).


### NIGHTLIES

A list of 3 nightlies (one per arch - x86_64, s390x, ppc64le) comma separated.

A nightly would be a release tag to pull from (e.g. 4.6.0-0.nightly-s390x-2020-11-06-181325).
These nightlies should be listed as `Accepted` in the release-controllers: \[
  [x86\_64](https://amd64.ocp.releases.ci.openshift.org/) |
  [s390x](https://s390x.ocp.releases.ci.openshift.org/) |
  [ppc64le](https://ppc64le.ocp.releases.ci.openshift.org/)
  \]

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

### RELEASE\_OFFSET

Releases are distinguished from others in the same minor version only by an integer offset.
This offset (call it X) is used to construct the release name depending on the release type:

1. Standard Release: `4.y.X`
2. Release Candidate: `4.y.0-rc.X`
3. Feature Candidate: `4.y.0-fc.X`
4. Hotfix: do not specify an offset; the name of the nightly is re-used.

## Known issues
As of right now (May 4th 2021) the job expects 3 nightlies always (for s390x, ppc64le and x86). In the future we want to fix this by varying for release type/version, and for supporting more arches. - [see this comment](https://github.com/openshift/aos-cd-jobs/pull/2606#discussion_r625391662) for details.
