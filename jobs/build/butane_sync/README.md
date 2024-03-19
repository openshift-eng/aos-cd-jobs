# butane_sync

## Purpose

Sync butane binaries to mirror.openshift.com.
(formerly the Fedora CoreOS Config Transpiler, FCCT)

<https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/butane/>

## Timing

Manually, upon request.

## Parameters

### NVR

NVR of the brew build from which binaries should be extracted.
Example: [butane-0.11.0-3.rhaos4.8.el8][]

### VERSION

Under which directory to place the binaries.
Example: v0.11.0

[butane-0.11.0-3.rhaos4.8.el8]: https://brewweb.engineering.redhat.com/brew/buildinfo?buildID=1592689]

### How does it work?

This job performs the following steps:

1. download all RPMs from a given brew build
2. extract the binaries from each RPM, appending the corresponding arch to each filename
3. create a `butane` symlink, pointing to the `butane-amd64` binary
4. calculate the shasum of each binary
5. sync them to https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/butane/, under a directory named
by the given version name.

### Example

Running the job with the following parameters:

* **NVR:** "butane-0.11.0-3.rhaos4.8.el8"
* **VERSION:** "v0.11.0"

Will download all RPMs from butane-0.11.0-3.rhaos4.8.el8:

    ├── butane-0.11.0-3.rhaos4.8.el8.aarch64.rpm
    ├── butane-0.11.0-3.rhaos4.8.el8.ppc64le.rpm
    ├── butane-0.11.0-3.rhaos4.8.el8.s390x.rpm
    ├── butane-0.11.0-3.rhaos4.8.el8.src.rpm
    ├── butane-0.11.0-3.rhaos4.8.el8.x86_64.rpm
    └── butane-redistributable-0.11.0-3.rhaos4.8.el8.noarch.rpm

Extract binaries from RPMs

    rpm2cpio <rpm> | cpio -idm ./usr/bin/butane

**NOTE:** `darwin-amd64` and `windows-amd64` are obtained from the redistributable "noarch" RPM;
Example: butane-redistributable-0.11.0-3.rhaos4.8.el8.noarch.rpm

    $ rpm -qlp butane-redistributable-0.11.0-3.rhaos4.8.el8.noarch.rpm
    /usr/share/butane-redistributable
    /usr/share/butane-redistributable/butane-darwin-amd64
    /usr/share/butane-redistributable/butane-windows-amd64.exe
    /usr/share/licenses/butane-redistributable
    /usr/share/licenses/butane-redistributable/LICENSE

The final result is published under a directory called v.0.11.0 with the following contents:

    ./v0.11.0
    ├── butane -> ./butane-amd64
    ├── butane-aarch64
    ├── butane-amd64
    ├── butane-darwin-amd64
    ├── butane-ppc64le
    ├── butane-s390x
    ├── butane-windows-amd64.exe
    └── sha256sum.txt
