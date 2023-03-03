#!/usr/bin/env groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib

    commonlib.describeJob("check-bugs", """
        ----------
        Check Bugs
        ----------
        Looks for blocker bugs and potential regressions, report findings on Slack.

        Timing: Daily run, scheduled.
    """)

    properties(
        [
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    string(
                        name: "SLACK_CHANNEL",
                        description: 'Slack channel to be notified in case of failures. ' +
                                    'Example: #art-automation-debug ' +
                                    'Leave blank to notify <strong>#forum-release</strong>',
                        defaultValue: '#forum-release',
                        trim: true,
                    )
                ]
            ]
        ]
    )

    // Check for mock build
    commonlib.checkMock()

    // Check bugs
    stage('check-bugs') {
        sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
            "check-bugs",
            "--slack_channel=${params.SLACK_CHANNEL}"
        ]
        for (String version : commonlib.ocpVersions) {
            cmd.add("--version")
            cmd.add(version)
        }
        for (String version : commonlib.ocpVersions) {
            if (is_prerelease(version)) {
                cmd.add("--pre_release")
                cmd.add(version)
            }
        }

        buildlib.withAppCiAsArtPublish() {
            withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'), string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                def returnStatus = sh(script: cmd.join(' '), returnStatus: true)
                if (returnStatus != 0) {
                    currentBuild.result = "UNSTABLE"
                }
            }
        }
    }
}

def is_prerelease(version) {
    try {
        return commonlib.ocpReleaseState[version]['release'].isEmpty()
    } catch (Exception e) {
        // there is no "version" release defined in ocpReleaseState
        return false
    }
}
