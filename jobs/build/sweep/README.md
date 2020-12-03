# Parameterized job for running bug and build sweeps

This job is run as a concluding part of the [ocp4], [ocp3], and [custom] jobs.
In that case, the aim is to get bugs that are in state `MODIFIED` to `ON_QA`.  To
run the job in this mode, keep `SWEEP_BUILDS` and `ATTACH_BUGS` as false (the
defaults).

The second mode is attach the latest bugs and builds to the release advisories.
To do that, set `SWEEP_BUILDS` and `ATTACH_BUGS` to true.


[ocp4]: https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/job/build%252Focp4/
[ocp3]: https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/job/build%252Focp3/
[custom]: https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/job/build%252Fcustom/
