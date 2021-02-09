# operator-sdk_sync

## Purpose

Sync operator-sdk binaries to mirror.openshift.com.

## Timing

Manually, upon request. Expected to happen once every y-stream and sporadically on z-stream releases.

## Parameters

### OCP_VERSION

Under which directory to place the binaries.
Examples:
- 4.7.0
- 4.7.0-rc.0

### BUILD_TAG

Build of ose-operator-sdk from which the contents should be extracted.
Examples:
- v4.7.0-202101261648.p0
- v4.7.0
- v4.7

## Known issues

### Job reports as 'SUCCESS' but sync to one of the mirrors failed

    [BEGIN] /usr/local/bin/push.pub.sh openshift-v4/ppc64le/clients/operator-sdk -v 2021-02-09 08:02:07
    [1] 08:37:07 [SUCCESS] mirror_sync@use-mirror2.ops.rhcloud.com
    [2] 08:37:07 [SUCCESS] mirror_sync@use-mirror1.ops.rhcloud.com
    [3] 08:37:08 [FAILURE] mirror_sync@use-mirror7.ops.rhcloud.com Exited with error code 12
    Statuses: [0, 0, 12]

Try again, otherwise open a ticket to OHSS.
Example: <https://issues.redhat.com/browse/OHSS-2099>.
