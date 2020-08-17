# Rebuild 4.x packages on RHEL8 for RHCOS

## Purpose

Whenever openshift and openshift-clients packages are built for el7, this job
takes the same content and rebuilds it under an el8 buildroot. RHCOS is the
only consumer of these builds. This keeps the kubelet and client versions for
both RHEL7 and RHCOS platforms as synchronized as possible.

> :information_souce: There are no concurrency controls because it is expected to be called
from within a job that already blocks concurrency per version.

## Timing

* The ocp4 job runs this immediately after building any RPMs.
* The custom job runs this only after building one of the packages in question.
* It should be very rare that a human runs this directly.

## Parameters

### Standard parameters BUILD\_VERSION, MOCK, SUPPRESS\_EMAIL

See [Standard Parameters](/jobs/README.md#standard-parameters).

### MAIL\_LIST\_FAILURE

(Optional) Comma-separated list of addresses to email when something fails.

## Known issues

### RHEL 8 builds sometimes have a different buildroot

Sometimes the RHEL 7 buildroot is fine and the RHEL 8 one is not (perhaps has the wrong version of golang).
In that case this job failing is often not noticed quickly.

See https://issues.redhat.com/browse/ART-1812

### Does not retry previously failed builds

This job works by copying dist-git content from the rhel-7 branch to the rhel-8 branch.
It only builds if there was new content to build. If it was copied already but the previous build failed,
it does not retry the build.

See https://issues.redhat.com/browse/ART-1812
