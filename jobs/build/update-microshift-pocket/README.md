Publishes the latest (or a specific version) of the microshift RPM to mirror.openshift.com into 
a "pocket". `mirror.openshift.com/pockets/microshift/` is the pocket used. A yum repo will
be created or updated when this job is run.

A pocket is delivery vehicle that is intended to provide artifacts to a select set of consumers
without access to every other pocket or /enterprise/*.
