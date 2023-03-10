Publishes a specific version of the microshift RPM to mirror.openshift.com.

A yum repo will be created or updated when this job is run.

If `UPDATE_PUB_MIRROR` is checked,  the artifacts will be published to a public location on the mirror: `/pub/openshift-v4/<ARCH>/microshift/ocp-dev-preview/<assembly-name>/el?/os/Packages/...`.
