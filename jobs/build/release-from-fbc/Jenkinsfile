#!/usr/bin/env groovy

import org.jenkinsci.plugins.workflow.steps.FlowInterruptedException

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("release-from-fbc", """
        Create releases from FBC (File-Based Catalogs) using artcd release-from-fbc command
    """)

    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                    commonlib.artToolsParam(),
                    string(
                        name: 'GROUP',
                        description: 'The group to use with artcd release-from-fbc command',
                        defaultValue: "oadp-1.3",
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The assembly version to create release for',
                        defaultValue: "1.3.8",
                        trim: true,
                    ),
                    text(
                        name: 'FBC_PULLSPECS',
                        description: 'Comma-separated list of FBC pullspecs (images) to create release from',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.enableTelemetryParam(),
                    commonlib.telemetryEndpointParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    if (currentBuild.description == null) {
        currentBuild.description = ""
    }
    sshagent(["openshift-bot"]) {
        stage("initialize") {
            currentBuild.displayName = "#${currentBuild.number} ${params.GROUP} ${params.ASSEMBLY}"
        }

        stage("release-from-fbc") {
            // artcd command
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
                "release-from-fbc",
                "--group",
                "${params.GROUP}",
                "--assembly",
                "${params.ASSEMBLY}",
                "--fbc-pullspecs",
                "${commonlib.cleanCommaList(params.FBC_PULLSPECS)}",
                "--create-mr"
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }

            // Needed to detect manual builds
            wrap([$class: 'BuildUser']) {
                builderEmail = env.BUILD_USER_EMAIL
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    file(credentialsId: 'openshift-bot-oadp-konflux-service-account', variable: 'OADP_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'openshift-bot-mta-konflux-service-account', variable: 'MTA_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'openshift-bot-mtc-konflux-service-account', variable: 'MTC_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'openshift-bot-logging-konflux-service-account', variable: 'LOGGING_KONFLUX_SA_KUBECONFIG'),
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    file(credentialsId: 'konflux-art-images-auth-file', variable: 'KONFLUX_ART_IMAGES_AUTH_FILE'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                ]){
                    def envVars = ["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']
                    if (params.TELEMETRY_ENABLED) {
                        envVars << "TELEMETRY_ENABLED=1"
                        if (params.OTEL_EXPORTER_OTLP_ENDPOINT && params.OTEL_EXPORTER_OTLP_ENDPOINT != "") {
                            envVars << "OTEL_EXPORTER_OTLP_ENDPOINT=${params.OTEL_EXPORTER_OTLP_ENDPOINT}"
                        }
                    }
                    withEnv(envVars) {
                        buildlib.init_artcd_working_dir()
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            // If any release creation failures occurred, mark the job run as unstable
                            currentBuild.result = "UNSTABLE"
                        }
                    }
                }
            }
        }

        stage("terminate") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.log",
                "artcd_working/**/*.yaml",
                "artcd_working/**/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }
}
