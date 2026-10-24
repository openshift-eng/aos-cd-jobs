#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("layered-products-prepare-release-unified", """
        <h2>Prepare ordinary or unified Layered Product releases</h2>
        Reads the assembly definition from <code>releases.yml</code>, triggers
        OLM bundle and FBC builds using the pinned operand NVRs, then creates
        a shipment MR in the GitLab shipment data repository.
        <br><br>
        In ordinary mode, the named assembly must already exist in ocp-build-data.
        Enable CREATE_UNIFIED_FBCS to prepare the highest numeric assembly from each
        comma-separated UNIFIED_FBC_GROUPS entry and ship one unified Quay FBC per OCP target.
        Leave GROUP and ASSEMBLY empty and REFRESH_FBCS disabled in unified mode.
        Use FORCE to consolidate existing source shipment MRs; all selected assemblies
        will point to the resulting shared shipment MR.
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
                    booleanParam(
                        name: 'CREATE_UNIFIED_FBCS',
                        description: 'Create product-wide unified Quay FBCs after preparing each selected group release.',
                        defaultValue: false,
                    ),
                    string(
                        name: 'UNIFIED_FBC_GROUPS',
                        description: 'Comma-separated Quay groups, e.g. quay-3.18,quay-3.17. Selects the highest numeric assembly in each releases.yml. Only used with CREATE_UNIFIED_FBCS.',
                        defaultValue: "",
                        trim: true,
                    ),
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
                    booleanParam(
                        name: 'FORCE',
                        description: 'Create a replacement shipment MR and update releases.yml. An open previous MR is closed; replacement is refused if it was merged or production was attempted.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'REFRESH_FBCS',
                        description: 'Force FBC rebuilds from the latest production catalogs before creating shipment data.',
                        defaultValue: false,
                    ),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    if (currentBuild.description == null) {
        currentBuild.description = ""
    }
    def unifiedGroups = commonlib.cleanCommaList(params.UNIFIED_FBC_GROUPS)
    if (params.CREATE_UNIFIED_FBCS) {
        if (params.GROUP?.trim() || params.ASSEMBLY?.trim() || params.REFRESH_FBCS) {
            error('CREATE_UNIFIED_FBCS cannot be used with GROUP, ASSEMBLY, or REFRESH_FBCS')
        }
        if (!unifiedGroups) {
            error('CREATE_UNIFIED_FBCS requires UNIFIED_FBC_GROUPS')
        }
    } else {
        if (unifiedGroups) {
            error('UNIFIED_FBC_GROUPS requires CREATE_UNIFIED_FBCS')
        }
        if (!params.GROUP?.trim() || !params.ASSEMBLY?.trim()) {
            error('GROUP and ASSEMBLY are required in ordinary mode')
        }
    }
    sshagent(["openshift-bot"]) {
        stage("initialize") {
            currentBuild.displayName = params.CREATE_UNIFIED_FBCS ?
                "#${currentBuild.number} unified ${unifiedGroups}" :
                "#${currentBuild.number} ${params.GROUP} ${params.ASSEMBLY}"
        }

        try {
            stage("layered-products-prepare-release-unified") {
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
                    "--create-mr"
                ]

                if (params.CREATE_UNIFIED_FBCS) {
                    cmd += ["--create-unified-fbcs", "--unified-fbc-groups", unifiedGroups]
                } else {
                    cmd += ["--group", params.GROUP.trim(), "--assembly", params.ASSEMBLY.trim()]
                }

                if (params.FORCE) {
                    cmd << "--force"
                }
                if (params.REFRESH_FBCS) {
                    cmd << "--refresh-fbcs"
                }

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
                        string(credentialsId: 'jira-bot-token', variable: 'JIRA_TOKEN'),
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
                        file(credentialsId: 'konflux-bot-0-art-quay-tenant-sa', variable: 'QUAY_KONFLUX_SA_KUBECONFIG'),
                    ]){
                        def envVars = ["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']
                        withEnv(envVars) {
                            buildlib.init_artcd_working_dir()
                            try {
                                sh(script: cmd.collect { "'" + it.toString().replace("'", "'\\''") + "'" }.join(' '), returnStdout: true)
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
                    "artcd_working/**/*.json",
                    "artcd_working/**/*.yaml",
                    "artcd_working/**/*.yml",
                ])
                buildlib.cleanWorkspace()
            }
        }
    }
    }
}
