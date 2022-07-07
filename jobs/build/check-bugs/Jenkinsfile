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
                    commonlib.jiraModeParam(),
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

        def env = ["KUBECONFIG=${buildlib.ciKubeconfig}"]
        if (params.JIRA_MODE) {
            env << "${params.JIRA_MODE}=True"
        }
        withEnv(env) {
            withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')]) {
                def out = sh(script: cmd.join(' '), returnStdout: true).trim()
                echo out

                if (out.contains('failed with')) {
                    currentBuild.result = "FAILURE"
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
