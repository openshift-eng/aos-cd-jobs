# WIP: OpenShift Pipeline Jobs
CI/CD jobs running on OpenShift, based on OpenShift Pipeline Build Strategy.

## Pipeline Jobs
Four pipeline jobs are created:
- *elliott-poll-tags* scheduled poll job, which triggers `elliott-release` job when a new release tag is created.
- *elliott-release* a job that creates an Elliott package and upload it to PyPI
- *doozer-poll-tags* scheduled poll job, which triggers `doozer-release` job when a new release tag is created.
- *doozer-release*  a job that creates a Doozer package and upload it to PyPI

## Jenkins deployment

Currently we enable permissive-script-security to allow all methods in the Jenkins groovy sandbox.

Example commands to deploy Jenkins on OpenShift (part of a Makefile):
```
create-jenkins-is:
	oc import-image jenkins:2 --confirm --scheduled=true \
		--from=registry.access.redhat.com/openshift3/jenkins-2-rhel7:v3.11
install-jenkins: create-jenkins-is
	oc new-app --template=jenkins-persistent \
		-p MEMORY_LIMIT=2Gi \
		-p VOLUME_CAPACITY=10Gi \
		-p NAMESPACE= \
		-e INSTALL_PLUGINS=script-security:1.70,permissive-script-security:0.6,timestamper:1.11 \
		-e JENKINS_JAVA_OVERRIDES=-Dpermissive-script-security.enabled=no_security
uninstall-jenkins:
    oc delete all,secret,sa,rolebinding,pvc -l app=jenkins-persistent
```

## Configure credentials
- PyPI username & password
``` bash
oc create secret generic art-pypi --from-literal=username=OpenShiftART --from-literal=password="some-password"
oc annotate --overwrite secret art-pypi "jenkins.openshift.io/secret.name=art-pypi"
oc label secret art-pypi credential.sync.jenkins.openshift.io=true
```

## Install/Update Pipeline Configs
``` bash
oc apply -f ./infra
oc apply -f ./jobs
```

## Build Images
```bash
oc start-build art-jenkins
oc start-build art-jenkins-slave
```

## Run polling jobs once to activate SCM polling
```bash
oc start-build elliott-poll-tags
oc start-build doozer-poll-tags
```

## Manually Trigger a pipeline run
``` bash
oc start-build elliott-release -e GIT_BRANCH=v1.0.0
oc start-build doozer-release -e GIT_BRANCH=v1.0.0
```
