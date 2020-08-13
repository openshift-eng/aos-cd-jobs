# Create the standard advisories for a new release

## Purpose

Implements [3.11.z](https://github.com/openshift/art-docs/blob/master/3.11.z.md#create-advisories) and [4.y.z](https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-advisories) advisory creation procedures.

A release consists of multiple advisories that should be created consistently.
* all need a fairly standard set of parameters
* some need placeholder bugs added
* all should be recorded in group.yml
* automation should be enabled to run builds for this version

Note that this will change significantly as part of the [Simplify 4.y releases](https://issues.redhat.com/browse/ART-2055) epic.

## Timing

The "release" job runs this as soon as the previous release for this version is
defined in the release-controller. Typically we will only need to run this
directly if that fails or is skipped, or when creating an initial GA release
for a version.

## Parameters

### Standard parameters DRY\_RUN, MOCK, SUPPRESS\_EMAIL, VERSION

See [Standard Parameters](/jobs/README.md#standard-parameters).

### REQUEST\_LIVE\_IDs

Send emails requesting live IDs to the docs team once advisories are created.
This is required for 4.y releases so that when creating a release image,
it can refer to the image advisory by the URL that it will have when shipped live.
(All advisories need live IDs eventually, but others only need it at ship time.)

Note: Does not send if SUPPRESS\_EMAIL is checked!

### ENABLE\_AUTOMATION

Unfreeze automation to enable building and sweeping into the new advisories.
This updates the freeze\_automation entry in the ocp-build-data branch for the
release.

Usually we want to do this - uncheck only if you know of a reason why we want
to keep the release closed to further changes.

### ASSIGNED\_TO

QE contact for advisories - unlikely to need anything but the default

### MANAGER

ART team manager (not release manager)

### PACKAGE\_OWNER

Must be an individual email address; may be anyone on the team who wants random advisory spam.

### IMPETUS

For which reason is the main advisory being created? This is recorded in
advisory metadata, although we're pretty much the only ones that ever read it.

* standard: this is almost always what you want, a regular old advisory.
* cve: this won't actually work now and will probably never have a use case.
* ga: use this for an initial GA of this version; makes the advisory a RHEA instead of RHBA
* test: use when testing the job actually creating advisories (not a dry run, and you'll still have to get them dropped afterward)

### DATE

Intended release date. Format: YYYY-Mon-dd (example: 2050-Jan-01)

### MAIL\_LIST\_FAILURE

Address(es) to mail when the job fails.

### LIVE\_ID\_MAIL\_LIST

When requesting a live ID for advisories, where to send the email.
Current default is OpenShift CCS Mailing List and OpenShift ART - it's unlikely to need anything but the default.

## Known issues

### Can't create RHSAs with this job

This job uses elliott to create advisories, and when creating a RHSA, elliott
currently requires a CVE tracker be supplied so that the advisory can be set up
with the flaw bug, importance set, text filled, etc.  We don't know that when
creating a release and anyway future process changes are coming in this area.

### REQUEST\_LIVE\_IDs incompatible with SUPPRESS\_EMAIL

No request email will be sent if SUPPRESS\_EMAIL is checked!
