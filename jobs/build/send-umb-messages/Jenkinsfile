#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

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
    releases = ["4-stable", "4.6.0-0.nightly", "4.5.0-0.nightly", "4.4.0-0.nightly", "4.3.0-0.nightly", "4.2.0-0.nightly", "4.1.0-0.nightly"]
    currentBuild.description = ""
    currentBuild.displayName = ""

    stage("send UMB messages for new releases") {
        dir ("/mnt/nfs/home/jenkins/.cache/releases") {
            for (String release : releases) {
                // There are different release controllers for OCP - one for each architecture.
                RELEASE_CONTROLLER_URL = commonlib.getReleaseControllerURL(release)
                latestRelease = sh(
                    returnStdout: true,
                    script: "curl -sf ${RELEASE_CONTROLLER_URL}/api/v1/releasestream/${release}/latest",
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
            }
        }
    }
}
