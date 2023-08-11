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

### UPDATE_LATEST_SYMLINK

Point "latest" symlink to version being published.
Usually, you'll only want to do that on the highest 4.x version.

## Known issues

None
