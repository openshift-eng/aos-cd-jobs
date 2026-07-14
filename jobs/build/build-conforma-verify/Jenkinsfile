#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("build-conforma-verify", """
        Run Conforma (Enterprise Contract) verification against OCP image builds.
        Accepts an OCP version and optional list of NVRs. If no NVRs are provided,
        the latest builds for the assembly are fetched automatically.
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
                    commonlib.ocpVersionParam('BUILD_VERSION', '4plus'),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to verify builds for',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    string(
                        name: 'BUILD_LIST',
                        description: '(Optional) Comma-separated list of NVRs to verify. If empty, latest builds for the assembly are fetched via elliott find-builds',
                        defaultValue: "",
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
                        name: 'EC_POLICY',
                        description: '(Optional) EnterpriseContractPolicy CR to use (namespace/name). Defaults to ocp-art-tenant/conforma-build-stage. Example: ocp-art-tenant/conforma-build-stage-test',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'INCLUDE_BUNDLES',
                        description: 'Also verify latest OLM bundle builds',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'INCLUDE_FBCS',
                        description: 'Also verify latest FBC (File-Based Catalog) builds',
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
    sshagent(["openshift-bot"]) {
        stage("initialize") {
            currentBuild.displayName = "${params.BUILD_VERSION} - #${currentBuild.number}"
        }

        stage("conforma-verify") {
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
                "build-conforma-verify",
                "--version=${params.BUILD_VERSION}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.DOOZER_DATA_PATH) {
                cmd << "--data-path=${params.DOOZER_DATA_PATH}"
            }
            if (params.DOOZER_DATA_GITREF) {
                cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
            }
            if (params.BUILD_LIST) {
                cmd << "--builds=${commonlib.cleanCommaList(params.BUILD_LIST)}"
            }
            if (params.EC_POLICY) {
                cmd << "--ec-policy=${params.EC_POLICY}"
            }
            if (params.INCLUDE_BUNDLES) {
                cmd << "--include-bundles"
            }
            if (params.INCLUDE_FBCS) {
                cmd << "--include-fbcs"
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    file(credentialsId: 'ocp-art-tenant', variable: 'KONFLUX_SA_KUBECONFIG'),
                    string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                    file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                    file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                ]) {
                    withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']) {
                        buildlib.init_artcd_working_dir()
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }
        }

        stage("terminate") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.log",
                "artcd_working/**/*.yaml",
                "artcd_working/**/*.yml",
                "artcd_working/**/results.yaml",
            ])
            buildlib.cleanWorkspace()
        }
    }
    }
}
