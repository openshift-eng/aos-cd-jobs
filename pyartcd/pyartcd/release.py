"""
Why is ocp_release_state needed?
To decide whether to build and use signed RPMs, and to decide if a strict
bug validation flow is necessary.
Before auto-signing, images were either built signed or unsigned.
Unsigned images were the norm and then, right before GA, we would rebuild
puddles and build as signed. In the new model, we always want to build
signed **if we plan on releasing the builds via an advisory**.
There are a category of builds that we DON'T plan on releasing through
an advisory. For a brand new release stream (or new arch) in 4.x, we want
to build nightlies and make them available as pre-release builds so that
even the general public can start experimenting with the new features of the release.
These pre-release images contain RPMs which have traditionally been unsigned.
We need them to continue to be unsigned!
Any code we sign using the auto-signing facility should be passed through
the errata process / rpmdiff.
Hence we need a very explicit source of truth on where our images are
destined. If it will ship via errata (state=release), we want to build signed. For
early access without an errata (state=pre-release).
For extra complexity, different architectures in a release can be in
different release states. For example, s390x might still be pre-release
even after x86_64 is shipping for a given 4.x. While we could theoretically build the
x86_64 image with signed RPMs, and s390x images with unsigned RPMS, OSBS
prohibits this since it considers it an error.
TODO: ask osbs to make this a configurable option?
Sooooo... when all arches are pre-release, we need to build unsigned. When any
arch is in release mode, we need to build all images with signed RPMs.
Why is release map information not in doozer metadata. It could be.
1) I think it would need some refactoring that won't be practical until
   the auto-signing work is validated.
2) We normally initialize a new doozer group by copying an old one. This
   release state could easily be copied unintentionally.
3) pre-release data is presently stored in poll-payload. This just tries
   to make it available for other jobs.
Alternatively, maybe this becomes the source of truth and confusing aspects like
'archOverrides' goes away in doozer config.
"""
ocp_release_state = {
    '4.14': {
        'release': [],
        'pre-release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
    },
    '4.13': {
        'release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
        'pre-release': [],
    },
    '4.12': {
        'release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
        'pre-release': [],
    },
    '4.11': {
        'release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
        'pre-release': [],
    },
    '4.10': {
        'release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
        'pre-release': [],
    },
    '4.9': {
        'release': ['x86_64', 's390x', 'ppc64le', 'aarch64'],
        'pre-release': [],
    },
    '4.8': {
        'release': ['x86_64', 's390x', 'ppc64le'],
        'pre-release': ['aarch64'],
    },
    '4.7': {
        'release': ['x86_64', 's390x', 'ppc64le'],
        'pre-release': ['aarch64'],
    },
    '4.6': {
        'release': ['x86_64', 's390x', 'ppc64le'],
        'pre-release': ['aarch64'],
    },
    '3.11': {
        'release': ['x86_64'],
        'pre-release': ['ppc64le', 's390x', 'aarch64'],
    },
}
