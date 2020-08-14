#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib

    commonlib.describeJob("crc_sync", """
        ----------------------------------------------
        Publish CodeReady Containers client to mirrors
        ----------------------------------------------
        https://developers.redhat.com/products/codeready-containers/overview

        Timing: Whenever the team asks us to do a release, typically with a new
        minor version GA.

        The CRC team will give us the URL for downloading the latest release,
        and the other parameters should be self-explanatory.
    """)

    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '30',
                    daysToKeepStr: '',
                    numToKeepStr: '30'
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'RELEASE_URL',
                        description: '(REQUIRED) Directory listing to latest release',
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: 'aos-art-automation+failed-crc-release@redhat.com',
                    ),
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Do not rsync the bits. Just download them and show what would have been copied',
                        defaultValue: false
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds(),
        ]
    )

    commonlib.checkMock()

    stage("Initialize") {
        buildlib.kinit()
        currentBuild.displayName = "CRC #${currentBuild.number} "
        currentBuild.description = params.RELEASE_URL
        build.initialize()
    }

    try {
        sshagent(["openshift-bot"]) {
            stage("Download release") { build.crcDownloadRelease() }
            stage("Rsync the release") { build.crcRsyncRelease() }
            stage("Push to mirrors") { build.crcPushPub() }
        }
    } catch (err) {
        currentBuild.result = "FAILURE"
        if (params.MAIL_LIST_FAILURE.trim()) {
            commonlib.email(
                to: params.MAIL_LIST_FAILURE,
                from: "aos-art-automation+failed-crc-release@redhat.com",
                replyTo: "aos-team-art@redhat.com",
                subject: "Error releasing Code Ready Containers",
                body: err,
            )
        }
        throw err  // gets us a stack trace FWIW
    } finally {
        commonlib.safeArchiveArtifacts([
                'email/*',
            ]
        )
    }
}
