Rebuilds 4.x openshift{,-clients} packages on RHEL8 for RHCOS.

Whenever openshift and openshift-clients packages are built for el7, this job
takes the same content and rebuilds it under an el8 buildroot. RHCOS is the
only consumer of these builds.

NOTE: There are no concurrency controls because it is expected to be called
from within a job that already blocks concurrency per version.
