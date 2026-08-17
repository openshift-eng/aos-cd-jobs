#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("release-payload", """
        <h2>Build OpenShift release payload images in Konflux</h2>
        <b>Timing</b>: Triggered automatically by promote-assembly after a successful promote.
        Can also be triggered manually.

        Invokes <code>artcd build-release-payload</code> to rebase
        the release payload source repo and trigger a Konflux build that produces a
        multi-arch manifest-list image. Cosigns the result after a successful sync.
    """)

    properties([
        disableResume(),
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '30',
                daysToKeepStr: '30',
                numToKeepStr: '300',
            )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.ocpVersionParam('VERSION', '4plus'),
                commonlib.artToolsParam(),
                string(
                    name: 'ASSEMBLY',
                    description: 'Assembly name to build the release payload for (e.g. 4.21.1 or stream).',
                    defaultValue: 'stream',
                    trim: true,
                ),
                string(
                    name: 'NVR',
                    description: 'If set, skip rebase and build — only sync this already-built payload NVR to quay.io. Requires a non-dry-run run.',
                    defaultValue: '',
                    trim: true,
                ),
                commonlib.dryrunParam('Do not push to git or trigger a Konflux build. Manifests are generated locally only.'),
                booleanParam(
                    name: 'SYNC',
                    description: 'After a successful build, mirror the release payload manifest list and every per-arch image to quay.io/openshift-release-dev/ocp-release (each pinned by its own sha256-<digest> tag). Requires a non-dry-run build (uses --push).',
                    defaultValue: false,
                ),
                commonlib.mockParam(),
            ],
        ]
    ])

    commonlib.checkMock()

    currentBuild.displayName += " ${params.VERSION} - ${params.ASSEMBLY}"
    if (params.DRY_RUN) {
        currentBuild.displayName += " [DRY RUN]"
    }

    stage("Validate parameters") {
        if (!params.VERSION?.trim()) {
            error("VERSION is required")
        }
        if (!params.ASSEMBLY?.trim()) {
            error("ASSEMBLY is required")
        }
        echo "Will build release payload:"
        echo "  group:    openshift-${params.VERSION}"
        echo "  assembly: ${params.ASSEMBLY}"
        echo "  NVR:      ${params.NVR ?: '(build new)'}"
        echo "  dry run:  ${params.DRY_RUN}"
        echo "  sync:     ${params.SYNC}"
    }

    def signing_env = params.DRY_RUN ? "stage" : "prod"
    def sigstore_creds_file = signing_env == "prod" ? "kms_prod_release_signing_creds_file" : "kms_stage_release_signing_creds_file"
    def sigstore_key_id = signing_env == "prod" ? "kms_prod_release_signing_key_id" : "kms_stage_release_signing_key_id"

    stage("build-release-payload") {
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
            "build-release-payload",
            "--group", "openshift-${params.VERSION}",
            "--assembly", params.ASSEMBLY,
        ]

        if (params.NVR?.trim()) {
            cmd += ["--nvr", params.NVR.trim()]
        }

        if (params.SYNC) {
            cmd << "--sync"
        }

        echo "Will run: ${cmd.join(' ')}"

        buildlib.withAppCiAsArtPublish() {
            withCredentials([
                file(credentialsId: 'konflux-bot-0-ocp-art-tenant-sa', variable: 'KONFLUX_SA_KUBECONFIG'),
                string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                usernamePassword(
                    credentialsId: 'art-dash-db-login',
                    passwordVariable: 'DOOZER_DB_PASSWORD',
                    usernameVariable: 'DOOZER_DB_USER'
                ),
                file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                file(credentialsId: sigstore_creds_file, variable: 'KMS_CRED_FILE'),
                string(credentialsId: sigstore_key_id, variable: 'KMS_KEY_ID'),
                string(credentialsId: 'signing_rekor_url', variable: 'REKOR_URL'),
            ]) {
                withEnv(['DOOZER_DB_NAME=art_dash', "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                    try {
                        buildlib.init_artcd_working_dir()
                        sh(script: cmd.join(' '))
                    } finally {
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

    }
}
