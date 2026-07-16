#!/usr/bin/env groovy

import org.jenkinsci.plugins.workflow.steps.FlowInterruptedException

node {
    timestamps {
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
                        description: 'The group to use (e.g. mta-8.1, logging-6.5, or openshift-4.22 with OCP_OPTIONAL)',
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
                    text(
                        name: 'JIRA_BUGS',
                        description: 'Comma-separated list of JIRA issue IDs to include in the advisory (e.g., OADP-7223,OADP-7222). Leave empty to skip.',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'TARGET_RELEASE_DATE',
                        description: 'Target ship date (e.g. 2026-Mar-31 or 2026-03-31). Included in shipment MR title. Leave empty to omit.',
                        defaultValue: "",
                        trim: true,
                    ),
                    text(
                        name: 'EXTRA_IMAGE_NVRS',
                        description: 'Comma-separated list of extra image NVRs to include in the image shipment file (not part of the FBC). At least one of FBC_PULLSPECS or EXTRA_IMAGE_NVRS must be provided.',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'OCP_OPTIONAL',
                        description: 'Enable OCP optional-operator mode. Creates extras/fbc shipments with all FBC related images included. Use with GROUP=openshift-4.x.',
                        defaultValue: false,
                    ),
                    string(
                        name: 'EXCLUDE_NVR_COMPONENTS',
                        description: '(Optional) Comma-separated NVR component names to explicitly exclude from shipment. Not needed in the default workflow.',
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
            if (params.DRY_RUN) {
                currentBuild.displayName += " [DRY_RUN]"
            }
        }

        try {
            stage("release-from-fbc") {
                def fbcPullspecs = commonlib.cleanCommaList(params.FBC_PULLSPECS)
                def extraImageNvrs = commonlib.cleanCommaList(params.EXTRA_IMAGE_NVRS)

                if (!fbcPullspecs && !extraImageNvrs) {
                    error("At least one of FBC_PULLSPECS or EXTRA_IMAGE_NVRS must be provided")
                }

                if (params.OCP_OPTIONAL && !params.GROUP.startsWith('openshift-')) {
                    error("OCP_OPTIONAL requires GROUP to start with 'openshift-' (e.g., openshift-4.22). " +
                          "Layered products (OADP, MTA, MTC, Logging) should use the default mode.")
                }

                if (!params.OCP_OPTIONAL && params.GROUP.startsWith('openshift-')) {
                    error("GROUP '${params.GROUP}' is an openshift-* group and requires OCP_OPTIONAL to be enabled. " +
                          "Without it, the default mode may filter out images and produce only FBC yaml.")
                }

                def cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=./artcd_working",
                    "--config=./config/artcd.toml",
                ]

                if (params.DRY_RUN) {
                    cmd << "--dry-run"
                }

                cmd += [
                    "release-from-fbc",
                    "--group",
                    "${params.GROUP}",
                    "--assembly",
                    "${params.ASSEMBLY}",
                    "--create-mr"
                ]

                if (fbcPullspecs) {
                    cmd += ["--fbc-pullspecs", fbcPullspecs]
                }
                if (extraImageNvrs) {
                    cmd += ["--extra-image-nvrs", extraImageNvrs]
                }

                def jiraBugs = commonlib.cleanCommaList(params.JIRA_BUGS)
                if (jiraBugs) {
                    cmd << "--jira-bugs"
                    cmd << "${jiraBugs}"
                }

                def targetDate = params.TARGET_RELEASE_DATE?.trim()
                if (targetDate) {
                    cmd << "--target-release-date"
                    cmd << "${targetDate}"
                }

                if (params.OCP_OPTIONAL) {
                    cmd << "--ocp-optional"
                }

                def excludeNvrComponents = commonlib.cleanCommaList(params.EXCLUDE_NVR_COMPONENTS)
                if (excludeNvrComponents) {
                    cmd << "--exclude-nvr-components"
                    cmd << "${excludeNvrComponents}"
                }

                // Needed to detect manual builds
                wrap([$class: 'BuildUser']) {
                    builderEmail = env.BUILD_USER_EMAIL
                }

                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                        string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                        string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                        file(credentialsId: 'konflux-bot-0-art-oadp-tenant-sa', variable: 'OADP_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-mta-tenant-sa', variable: 'MTA_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-mtc-tenant-sa', variable: 'MTC_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-logging-tenant-sa', variable: 'LOGGING_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-oap-tenant-sa', variable: 'OAP_KONFLUX_SA_KUBECONFIG'),
                        string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                        string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                        string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                        file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                        file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                        string(credentialsId: 'art-bot-jenkins-gitlab', variable: 'GITLAB_TOKEN'),
                        string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                        file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
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
        } finally {
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
    }
}
