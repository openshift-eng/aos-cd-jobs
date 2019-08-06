#!/usr/bin/env groovy

node {
    properties([
        disableConcurrentBuilds(),
    ])

    // we only care to publish messages for the following releases
    releases = ["4-stable", "4.2.0-0.nightly"]

    stage("send UMB messages for new releases") {
        dir ("~/.cache/releases") {
            for (String release : releases) {
                latestRelease = sh(
                    returnStdout: true,
                    script: "curl -s https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/${release}/latest",
                ).trim()
                previousRelease = readFile("${release}.current")
                if ( latestRelease != previousRelease ) {
                    sendCIMessage(
                        messageContent: "New release payload for OpenShift ${release}",
                        messageProperties: "${latestRelease}",
                        messageType: 'custom',
                        overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                        providerName: 'Red Hat UMB'
                    )
                    writeFile file: "${release}.current", text: "${latestRelease}"
                }
            }
        }
    }
}
