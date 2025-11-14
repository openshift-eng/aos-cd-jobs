#!/usr/bin/env groovy

import org.jenkinsci.plugins.workflow.steps.FlowInterruptedException

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("oadp", """
        Build images for OADP / MTC
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
                    booleanParam(
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        defaultValue: false
                    ),
                    string(
                        name: 'GROUP',
                        description: 'The OADP version group to use with -g flag',
                        defaultValue: "oadp-1.5",
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to rebase & build for',
                        defaultValue: "test",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'IMAGE_LIST',
                        description: 'Comma/space-separated list of image names to build',
                        defaultValue: "oadp-operator",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'SKIP_REBASE',
                        description: '(For testing) Skip the rebase step',
                        defaultValue: false
                    ),
                    choice(
                        name: 'NETWORK_MODE',
                        description: 'Override network mode for Konflux builds',
                        choices: [
                            "",
                            "hermetic",
                            "internal-only",
                            "open"
                        ].join("\n")
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
            currentBuild.displayName = "#${currentBuild.number} ${params.GROUP}"
        }

        stage("build") {
            // artcd command
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
                "build-oadp",
                "-g",
                "${params.GROUP}",
                "--assembly=${params.ASSEMBLY}",
                "--data-path=${params.DOOZER_DATA_PATH}"
            ]
            if (params.DOOZER_DATA_GITREF) {
                cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
            }
            if (params.IGNORE_LOCKS) {
                cmd << "--ignore-locks"
            }
            if (params.SKIP_REBASE) {
                cmd << "--skip-rebase"
            }
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            if (params.NETWORK_MODE && params.NETWORK_MODE != "") {
                cmd << "--network-mode=${params.NETWORK_MODE}"
            }
            
            cmd += [
                "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}",
            ]

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
                            file(credentialsId: 'creds_registry.redhat.io', variable: 'KONFLUX_OPERATOR_INDEX_AUTH_FILE'),
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
                            // If any image build/push failures occurred, mark the job run as unstable
                            currentBuild.result = "UNSTABLE"
                        }
                    }
                }
            }
        }

        stage("terminate") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.log",
                "artcd_working/doozer_working/*.yaml",
                "artcd_working/doozer_working/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }
}
