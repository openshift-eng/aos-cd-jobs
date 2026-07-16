#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("layered-products-prepare-release", """
        <h2>Prepare a Layered Product release from a named assembly</h2>
        Reads the assembly definition from <code>releases.yml</code>, triggers
        OLM bundle and FBC builds using the pinned operand NVRs, then creates
        a shipment MR in the GitLab shipment data repository.
        <br><br>
        The assembly must already exist in ocp-build-data (created by layered-products-gen-assembly).
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
                    string(
                        name: 'GROUP',
                        description: 'The group to use (e.g. acm-2.17, mce-2.17)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The named assembly to prepare (e.g. 2.17.3). Must exist in releases.yml.',
                        defaultValue: "",
                        trim: true,
                    ),
                    text(
                        name: 'JIRA_BUGS',
                        description: '(Optional) Comma-separated JIRA issue IDs for release notes (e.g. ACM-1234,ACM-5678)',
                        defaultValue: "",
                    ),
                    string(
                        name: 'TARGET_RELEASE_DATE',
                        description: '(Optional) Target ship date (e.g. 2026-Mar-31 or 2026-03-31). Included in MR title.',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'BUILD_DATA_REPO_URL',
                        description: 'ocp-build-data pull URL (default: openshift-eng/ocp-build-data)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'SHIPMENT_DATA_REPO_URL',
                        description: '(Optional) GitLab shipment data repo URL override.',
                        defaultValue: "",
                        trim: true,
                    ),
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

        try {
            stage("layered-products-prepare-release") {
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
                    "prepare-release-lp",
                    "--group", "${params.GROUP}",
                    "--assembly", "${params.ASSEMBLY}",
                    "--create-mr"
                ]

                def buildDataUrl = params.BUILD_DATA_REPO_URL?.trim()
                if (buildDataUrl) {
                    cmd += ["--build-data-repo-url", buildDataUrl]
                }

                def shipmentDataUrl = params.SHIPMENT_DATA_REPO_URL?.trim()
                if (shipmentDataUrl) {
                    cmd += ["--shipment-data-repo-url", shipmentDataUrl]
                }

                def jiraBugs = commonlib.cleanCommaList(params.JIRA_BUGS)
                if (jiraBugs) {
                    cmd += ["--jira-bugs", jiraBugs]
                }

                def targetDate = params.TARGET_RELEASE_DATE?.trim()
                if (targetDate) {
                    cmd += ["--target-release-date", targetDate]
                }

                wrap([$class: 'BuildUser']) {
                    builderEmail = env.BUILD_USER_EMAIL
                }

                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                        string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                        string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                        string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                        string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                        string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                        file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                        file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                        file(credentialsId: 'creds_registry.redhat.io', variable: 'KONFLUX_OPERATOR_INDEX_AUTH_FILE'),
                        string(credentialsId: 'art-bot-jenkins-gitlab', variable: 'GITLAB_TOKEN'),
                        string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                        file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                        file(credentialsId: 'konflux-bot-0-art-logging-tenant-sa', variable: 'LOGGING_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-oadp-tenant-sa', variable: 'OADP_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-mta-tenant-sa', variable: 'MTA_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-mtc-tenant-sa', variable: 'MTC_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-acm-tenant-sa', variable: 'ACM_KONFLUX_SA_KUBECONFIG'),
                        file(credentialsId: 'konflux-bot-0-art-oap-tenant-sa', variable: 'OAP_KONFLUX_SA_KUBECONFIG'),
                    ]){
                        def envVars = ["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']
                        withEnv(envVars) {
                            buildlib.init_artcd_working_dir()
                            try {
                                sh(script: cmd.join(' '), returnStdout: true)
                            } catch (err) {
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
