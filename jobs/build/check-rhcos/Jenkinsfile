#!/usr/bin/env groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib

    commonlib.describeJob("check-rhcos", """
        ----------
        Check RHCOS
        ----------
        Checks RHCOS jenkins pipelines for their status, and compiles that into a png,
        and posts it to slack channel.

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
                        description: 'Slack channel to be notified in case of failures.',
                        defaultValue: '#jenkins-coreos',
                        trim: true,
                    )
                ]
            ]
        ]
    )

    commonlib.checkMock()

    stage('check-rhcos') {
        sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
            "check-rhcos",
            "--slack-channel=${params.SLACK_CHANNEL}"
        ]

        withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')]) {
            commonlib.shell(script: cmd.join(' '))
        }
    }
}
