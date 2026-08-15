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

        Invokes <code>doozer beta:release-payload:rebase-and-build</code> to rebase
        the release payload source repo and trigger a Konflux build that produces a
        multi-arch manifest-list image.
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

    def payloadRelease = new Date().format("yyyyMMddHHmm", TimeZone.getTimeZone('UTC')) + ".p2"

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
        echo "  group:           openshift-${params.VERSION}"
        echo "  assembly:        ${params.ASSEMBLY}"
        echo "  payload release: ${payloadRelease}"
        echo "  dry run:         ${params.DRY_RUN}"
        echo "  sync:            ${params.SYNC}"
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        buildlib.oc("version --client=true -o yaml")
    }

    def doozer_working = "${env.WORKSPACE}/doozer_working"

    stage("Build release payload") {
        buildlib.cleanWorkdir(doozer_working)

        def cmd = [
            "doozer",
            "--group", "openshift-${params.VERSION}",
            "--assembly", params.ASSEMBLY,
        ]

        cmd += [
            "beta:release-payload:rebase-and-build",
            "--release", payloadRelease,
            "--registry-config", '${QUAY_AUTH_FILE}',
        ]

        if (params.DRY_RUN) {
            cmd << "--dry-run"
        } else {
            cmd << "--push"
            if (params.SYNC) {
                cmd << "--sync"
            }
        }

        echo "Will run: ${cmd.join(' ')}"

        try {
            dir(doozer_working) {
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
                    ]) {
                        withEnv(['DOOZER_DB_NAME=art_dash', "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                            sh(script: cmd.join(' '))
                        }
                    }
                }
            }
        } finally {
            commonlib.safeArchiveArtifacts([
                "doozer_working/debug.log",
                "doozer_working/**/*.log",
                "doozer_working/**/*.json",
            ])
            buildlib.cleanWorkspace()
        }
    }

    }
}
