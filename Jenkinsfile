#!/usr/bin/env groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib

    commonlib.describeJob("cleanup-locks", """
        ----------
        Cleanup locks
        ----------
        Clean up locks that might stay locked after cancelling jobs by hand.

        Timing: Triggered by jobs on user interruption:
        - ocp4
    """)

    properties(
        [
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.artToolsParam()
                ]
            ]
        ]
    )

    // Check for mock build
    commonlib.checkMock()

    // Clean up locks
    stage('cleanup-locks') {
        buildlib.init_artcd_working_dir()
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
            "cleanup-locks",
        ]

        withCredentials([
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN')
                ]) {
            withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                try {
                    sh(script: cmd.join(' '), returnStdout: true)
                } catch (err) {
                    throw err
                } finally {
                    commonlib.safeArchiveArtifacts([
                        "artcd_working/**/*.log",
                    ])
                }
            }
        }
    }
}
