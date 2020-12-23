# Mirror latest 4.y images to nightlies

## Purpose

This job gets the latest payload images from our candidate tags, syncs them to
quay.io/openshift-release-dev/ocp-v4.0-art-dev where we publish payload members
for all 4.y versions, and updates the arch-specific imagestreams on api.ci
(which feed into nightlies on our release-controllers) to point at the updated
(arch-specific) image shasum.

Example imagestreams:

* [`4.5 x86_64`](https://api.ci.openshift.org/console/project/ocp/browse/images/4.5-art-latest/)
* [`4.4 s390x`](https://api.ci.openshift.org/console/project/ocp-s390x/browse/images/4.4-art-latest-s390x)
* [`4.6 ppc64le`](https://api.ci.openshift.org/console/project/ocp-ppc64le/browse/images/4.6-art-latest-ppc64le)

## Timing

This will nearly always be run by the ocp4 or custom job.

A human might want to run this after hand-adjusting the current tagged images
in brew in order to update the nightlies accordingly. Another option is to sync
images from a past brew event in order to turn back time on the nightly.

## Artifacts

Among the archived artifacts for this job are the arch-specific imagestream
definitions that specify the contents of nightlies. These can be useful for
monkeying with the contents by hand, for example to [trigger a new nightly](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#what-to-do-if-the-latest-nightly-is-rejected-).
(Although such monkeying for any other reason is probably unwise, and tedious
for multiple arches.)

## Parameters

### Standard parameters BUILD\_VERSION, DRY\_RUN, MOCK, SUPPRESS\_EMAIL

See [Standard Parameters](/jobs/README.md#standard-parameters).

### DEBUG

Run "oc" commands with greater logging if they seem to be doing something funny.

### IMAGES

[List](/jobs/README.md#list-parameters) of image distgits to sync.
If not specified, the default is to sync every image.
This can be useful for testing purposes or for hand-crafted updates, because
syncing all images takes a great deal longer than a handful.

You will usually want to include the openshift-enterprise-cli distgit (see below).

### BREW\_EVENT\_ID

Look for the last images as of the given Brew event instead of latest; turn back time.
Note that this does nothing to alter the machine-os-content (RHCOS) image in the nightly.

### ORGANIZATION

Quay.io organization to mirror to - there is no reason to ever change this.

### REPOSITORY

Quay.io repository to mirror to - there is no reason to ever change this.

## Known issues

### Multiarch sync must include openshift-enterprise-cli image

The cluster version operator (CVO) requires that all named images be present in
the payload, or it fails the cluster bootstrap. However, some payload images
are unavailable on some architectures. In order to keep the CVO from flagging
this, we sync a "dummy" image in place of missing images for an architecture.
We have chosen the `cli` image (that is, the `openshift-enterprise-cli`
distgit) for our dummy image in these cases, since it is available for all
arches and contains useful binaries for determining what it is if someone is
confused about the whole dummy image substitution.

The result is that build-sync requires that `openshift-enterprise-cli` be included in what is synced.
This is true even if no substitution is needed, because the job looks up that image before attempting any syncing.

Usually this is no problem since the `cli` image is available. There are two cases where it's not:

1. When building from a newly branched release and this image hasn't built yet.
   In this case, either get the image building, or just tag in one from the previous release in brew.
2. When building a subset of images that doesn't include it. Just make sure to include it.

### Sometimes it doesn't actually update the imagestreams

This seems to be an oc bug, and could be fixed by now. But sometimes when we
`oc apply` the updated imagestream, everything seems to work, but we find the
imagestream isn't actually updated. Naturally we always notice this when we're
trying to get a release out at the last second.

It seems to work if we take the imagestream definitions from the job artifacts
and hand-apply them like so on as jenkins user on buildvm:

    /usr/bin/oc apply --config /home/jenkins/kubeconfigs/art-publish.app.ci.kubeconfig --filename=./is.s390x.doctored.yaml

