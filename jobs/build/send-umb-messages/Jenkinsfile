#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("send-umb-messages", """
        ----------------------------------------------------------
        Send UMB messages when new releases/nightlies are accepted
        ----------------------------------------------------------
        Timing: Scheduled to run about every 5 minutes.

        This job checks the x86_64 release-controller for newly-accepted
        release images and publishes a UMB message that others can use to
        trigger their automation (e.g. QE can trigger testing).
    """)


    properties([
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '30',
                    numToKeepStr: ''
                )
            ),
            disableResume(),
            disableConcurrentBuilds(),
    ])

    // we only care to publish messages for the following releases
    releases = commonlib.ocp4SendUMBVersions
    currentBuild.description = ""
    currentBuild.displayName = ""

    stage("send UMB messages for new releases") {
        dir ("/mnt/nfs/home/jenkins/.cache/releases") {
            for (String release : releases) {
                try {
                    // There are different release controllers for OCP - one for each architecture.
                    RELEASE_CONTROLLER_URL = commonlib.getReleaseControllerURL(release)
                    latestRelease = sh(
                        returnStdout: true,
                        script: "curl -L -sf ${RELEASE_CONTROLLER_URL}/api/v1/releasestream/${release}/latest",
                    ).trim()
                    latestReleaseVersion = readJSON(text: latestRelease).name
                    echo "${release}: latestRelease=${latestRelease}"
                    try {
                        previousRelease = readFile("${release}.current")
                        echo "${release}: previousRelease=${previousRelease}"
                    } catch (readex) {
                        // The first time this job is ran and the first
                        // time any new release is added the 'readFile'
                        // won't find the file and will raise a
                        // NoSuchFileException exception.
                        echo "${release}: Error reading revious release: ${readex}"
                        touch file: "${release}.current"
                        previousRelease = ""
                    }

                    if ( latestRelease != previousRelease ) {
                        def previousReleaseVersion = "0.0.0"
                        if (previousRelease)
                            previousReleaseVersion = readJSON(text: previousRelease).name
                            currentBuild.displayName += "🆕 ${release}: ${previousReleaseVersion} -> ${latestReleaseVersion}"
                            currentBuild.description += "\n🆕 ${release}: ${previousReleaseVersion} -> ${latestReleaseVersion}"

                        sendCIMessage(
                            messageProperties: "release=${release}",
                            messageContent: latestRelease,
                            messageType: 'Custom',
                            failOnError: true,
                            overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                            providerName: 'Red Hat UMB'
                        )
                        writeFile file: "${release}.current", text: "${latestRelease}"
                    } else {
                        currentBuild.description += "\nUnchanged: ${release}"
                    }
                } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException ex) {
                    // don't try to recover from cancel
                    throw ex
                } catch (ex) {
                    // but do tolerate other per-release errors
                    echo "Error during release ${release}: ${ex}"
                    currentBuild.description += "\nFailed: ${release}"
                }
            }
        }
    }
}
