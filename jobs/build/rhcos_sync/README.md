Publishes RHCOS bootimages to mirror (`mirror.openshift.com/pub/openshift-v4/x86_64/dependencies/rhcos/`). 
The RHCOS build reference either comes from the installer image in the release specified (**note**: this reference is often different than the rhcos image (mosc/rhel-coreos) in the release payload) OR can be specified in the job params.

This happens as part of every GA release ([https://art-docs.engineering.redhat.com/release/4.y-ga/#publish-rhcos-bootimages]), but not for every z-stream release. To request bootimages be published for a z-release, a subtask should be created in the relevant release ticket with the buildid to be synced ((example)[https://issues.redhat.com/browse/ART-5993])

Typical use is to set the `FROM_RELEASE_TAG` to a value like `4.12.3-x86_64`,
and leave the other fields to their defaults.
