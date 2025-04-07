# Mirror latest 4.y images to nightlies

## Purpose

This job gets the latest payload images from our candidate tags, syncs them to
quay.io/openshift-release-dev/ocp-v4.0-art-dev where we publish payload members
for all 4.y versions, and updates the arch-specific imagestreams on api.ci
(which feed into nightlies on our release-controllers) to point at the updated
(arch-specific) image shasum.

Before announcing a new assembly on api.ci, a comprehensive set of internal
consistency checks is executed. Build-sync may decide not to create a new entry
in api.ci because of this, and should be considered the ultimate artbiter.

Example imagestreams:

* [`4.19 x86_64`](https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/k8s/ns/ocp/imagestreams/4.19-art-latest)
* [`4.20 s390x`](https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/k8s/ns/ocp-s390x/imagestreams/4.20-art-latest-s390x)
* [`4.19 arm64 priv`](https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/k8s/ns/ocp-arm64-priv/imagestreams/4.19-art-latest-arm64-priv)


## Timing

This will nearly always be run by the `ocp4` job.

A human might want to run this after hand-adjusting the current tagged images
in brew in order to update the nightlies accordingly. Another option is to sync
images from an assembly.

## Artifacts

Among the archived artifacts for this job are the arch-specific imagestream
definitions that specify the contents of nightlies. These can be useful for
monkeying with the contents by hand, for example to [trigger a new nightly](https://art-docs.engineering.redhat.com/release/4.y.z-stream/#what-to-do-if-the-latest-nightly-is-rejected).
(Although such monkeying for any other reason is probably unwise, and tedious
for multiple arches.)

## Parameters

### Standard parameters ASSEMBLY, BUILD\_VERSION, DOOZER\_DATA\_PATH, DRY\_RUN, MOCK, SUPPRESS\_EMAIL

See [Standard Parameters](/jobs/README.md#standard-parameters).

### RETRIGGER\_CURRENT\_NIGHTLY

Force the release controller to re-create the latest nightly for the version
with existing images; no change will be made to payload images in the release,
and all other parameters will be ignored.

### PUBLISH

This is intended for publishing a release image for assemblies (which would not
otherwise get an entry on the release-controller). An image per arch will be
published to registry.ci like nightlies -- the job description will list the
locations.

### DEBUG

Run "oc" commands with greater logging if they seem to be doing something funny.

### IMAGES

[List](/jobs/README.md#list-parameters) of image distgits to sync.
If not specified, the default is to sync every image.
This can be useful for testing purposes or for hand-crafted updates, because
syncing all images takes a great deal longer than a handful.

You will usually want to include the openshift-enterprise-pod distgit (see below).

### EXCLUDE\_ARCHES

[List](/jobs/README.md#list-parameters) of architectures NOT to sync.
If not specified, the default is to sync every arch that is built for any image.

Sometimes when we are turning arches on and off, it is inconvenient to require
all the previously-built images to have all arches built (this usually requires
a full rebuild). With this parameter we can ignore "problematic" arches.

### EMERGENCY\_IGNORE\_ISSUES

Ignore the results of the consistency checks and sync out whatever we have
anyway. Obviously, this should never be necessary; in most cases we should
update the `releases.yml` `permits` field for the assembly instead, and for GA
versions we should never be producing inconsistent nightlies. So use this only
with approval from team leadership.

### ORGANIZATION

Quay.io organization to mirror to - there is no reason to ever change this.

### REPOSITORY

Quay.io repository to mirror to - there is no reason to ever change this.

## Known issues

### Multiarch sync must include openshift-enterprise-pod image

The cluster version operator (CVO) requires that all named images be present in
the payload, or it fails the cluster bootstrap. However, some payload images
are unavailable on some architectures. In order to keep the CVO from flagging
this, we sync a "dummy" image in place of missing images for an architecture.
We have chosen the `pod` image (that is, the `openshift-enterprise-pod`
distgit) for our dummy image in these cases, since it is available for all
arches and contains useful binaries for determining what it is if someone is
confused about the whole dummy image substitution.

The result is that build-sync requires that `openshift-enterprise-pod` be included in what is synced.
This is true even if no substitution is needed, because the job looks up that image before attempting any syncing.

Usually this is no problem since the `pod` image is available. There are two cases where it's not:

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

