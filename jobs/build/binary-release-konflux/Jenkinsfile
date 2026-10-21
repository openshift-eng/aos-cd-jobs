#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("binary-release-konflux", """
        <h2>Release a standalone CDN binary product built via Konflux</h2>
        <b>Timing</b>: Run manually once a build NVR is ready to ship.

        Takes a Konflux build NVR for a supported binary product (e.g. oc-mirror) and
        creates a shipment MR in ocp-shipment-data referencing that product's CDN
        stage/prod ReleasePlans, using the artcd binary-release-konflux command.
    """)

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
                    [
                        name: 'PRODUCT',
                        description: 'The binary product to release. Maps to the ocp-build-data group name.',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            'oc-mirror-2.0',
                            'mirror-gui-1.0',
                            'openshift-4.12',
                            'openshift-4.13',
                            'openshift-4.14',
                            'openshift-4.15',
                            'openshift-4.16',
                            'openshift-4.17',
                            'openshift-4.18',
                            'openshift-4.19',
                            'openshift-4.20',
                            'openshift-4.21',
                            'openshift-4.22',
                            'openshift-4.23',
                            'openshift-5.0',
                            'openshift-5.1',
                        ].join('\n'),
                    ],
                    string(
                        name: 'ASSEMBLY',
                        description: 'The assembly to create the release for',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    text(
                        name: 'NVR',
                        description: 'Comma-separated list of build NVR(s) to release, e.g. oc-mirror-container-2.0-202607291654.p2.g90b54b1.assembly.stream.el9',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'RELEASE_PLAN_KEY',
                        description: 'ocp-shipment-data config.yaml applications key for the stage/prod ReleasePlans. Required for openshift-* products: openshift-X-Y-binaries (GA) or openshift-X-Y-binaries-dev-preview. Leave empty for other products.',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'SHIPMENT_KIND',
                        description: 'Shipment file kind. Required for openshift-* products: binaries (GA) or binaries-dev-preview. Leave empty for other products (default kind: image).',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'TARGET_RELEASE_DATE',
                        description: 'Target ship date (e.g. 2026-Mar-31 or 2026-03-31). Included in shipment MR title. Leave empty to omit.',
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
            currentBuild.displayName = "#${currentBuild.number} ${params.PRODUCT} ${params.ASSEMBLY}"
            if (params.DRY_RUN) {
                currentBuild.displayName += " [DRY_RUN]"
            }
        }

        try {
            stage("binary-release-konflux") {
                def nvrs = commonlib.cleanCommaList(params.NVR)

                if (!nvrs) {
                    error("NVR must contain at least one build NVR to release")
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
                    "binary-release-konflux",
                    "--group",
                    "${params.PRODUCT}",
                    "--assembly",
                    "${params.ASSEMBLY}",
                    "--nvrs",
                    nvrs,
                    "--create-mr"
                ]

                def releasePlanKey = params.RELEASE_PLAN_KEY?.trim()
                if (releasePlanKey) {
                    cmd << "--release-plan-key"
                    cmd << "${releasePlanKey}"
                }

                def shipmentKind = params.SHIPMENT_KIND?.trim()
                if (shipmentKind) {
                    cmd << "--shipment-kind"
                    cmd << "${shipmentKind}"
                }

                def targetDate = params.TARGET_RELEASE_DATE?.trim()
                if (targetDate) {
                    cmd << "--target-release-date"
                    cmd << "${targetDate}"
                }

                // Needed to detect manual builds
                wrap([$class: 'BuildUser']) {
                    builderEmail = env.BUILD_USER_EMAIL
                }

                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                        string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                        string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                        file(credentialsId: 'konflux-bot-0-ocp-art-tenant-sa', variable: 'KONFLUX_SA_KUBECONFIG'),
                        string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
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
                            sh(script: cmd.join(' '), returnStdout: true)
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
