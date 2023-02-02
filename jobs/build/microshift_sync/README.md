Publishes a specific version of the microshift RPM to mirror.openshift.com.

A yum repo will be created or updated when this job is run.

If `UPDATE_POCKET` is checked, the artifacts will be published into a "pocket". `mirror.openshift.com/pockets/microshift/` is the pocket used. A pocket is delivery vehicle that is intended to provide artifacts to a select set of consumers
without access to every other pocket or `/enterprise/*`.

If `UPDATE_POCKET` is checked,  the artifacts will be published to a public location on the mirror: `/pub/openshift-v4/<ARCH>/microshift/ocp-dev-preview/<assembly-name>/el?/os/Packages/...`.
