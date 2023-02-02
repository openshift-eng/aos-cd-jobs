node {
    checkout scm
    buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib
    slacklib = commonlib.slacklib

    properties( [
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '100', daysToKeepStr: '', numToKeepStr: '100')),
        disableConcurrentBuilds(),
        disableResume(),
    ] )

    def versionJobs = [:]
    for ( version in commonlib.ocp4Versions ) {
        def cv = "${version}" // make sure we use a locally scoped variable

        // Skip the build if already locked
        activityLockName = "github-activity-lock-${cv}"
        if (!commonlib.canLock(activityLockName)) {
            echo "Looks like there is another build ongoing for ${cv} -- skipping for this run"
            continue
        }

        // Trigger ocp4-scan build for ${version}
        versionJobs["scan-v${version}"] = {
            try {
                timeout(activity: true, time: 30, unit: 'MINUTES') {
                    build job: '../aos-cd-builds/build%2Focp4_scan', parameters: [string(name: 'VERSION', value: "${cv}")], propagate: false
                }
            } catch (te) {
                slacklib.to(cv).failure("Error running ocp_scan", te)
            }
        }
    }

    parallel versionJobs
}
