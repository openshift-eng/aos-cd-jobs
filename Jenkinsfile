#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("base-image-release", """
        <h2>Release base images to base repository</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.

        Supply exactly one Konflux IMAGE build <code>NVR</code> (SUCCESS row required for this group —
        ART-18934 / art-tools). The job invokes <code>doozer images:release-to-base-repo</code>
        once with singular <code>--nvr</code>.
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
                commonlib.suppressEmailParam(),
                commonlib.mockParam(),
                string(
                    name: 'BUILD_VERSION',
                    description: 'Build group name (e.g., openshift-5.0 for OCP or rhel-9-golang-1.24 for golang builders)',
                    defaultValue: "openshift-5.0",
                    trim: true,
                ),
                commonlib.artToolsParam(),
                string(
                    name: 'ASSEMBLY',
                    description: 'The name of an assembly to use.',
                    defaultValue: "stream",
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
                    name: 'NVR',
                    description: 'Exactly one Konflux IMAGE build NVR for this group (SUCCESS row required). Passed once to images:release-to-base-repo --nvr.',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name: 'DRY_RUN',
                    description: 'When true, invoke doozer with global --dry-run. Snapshot/release semantics for images:release-to-base-repo depend on art-tools honoring that flag; confirm behavior before trusting it for risky runs.',
                    defaultValue: false,
                ),
            ],
        ]
    ])

    commonlib.checkMock()

    stage('Validate Parameters') {
        if (!params.NVR?.trim()) {
            error('NVR is required — exactly one Konflux IMAGE build NVR (no comma-separated lists; run this job separately per release).')
        }
        def trimmed = params.NVR.trim()
        if (trimmed.contains(',')) {
            error('Use a single NVR only; commas are not supported (spawn another job build for additional NVRs).')
        }
        env.BASE_IMAGE_RELEASE_NVR = trimmed

        echo("Single-NVR images:release-to-base-repo (--nvr) run.")
        echo("Base Image Release Parameters:")
        echo("  BUILD_VERSION: ${params.BUILD_VERSION}")
        echo("  ASSEMBLY: ${params.ASSEMBLY}")
        echo("  NVR: ${env.BASE_IMAGE_RELEASE_NVR}")
        echo("  DRY_RUN: ${params.DRY_RUN}")

        currentBuild.displayName = "${params.BUILD_VERSION} - ${env.BASE_IMAGE_RELEASE_NVR}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        buildlib.elliott "--version"
        buildlib.oc("version --client=true -o yaml")
    }

    stage("Release base image") {
        doozer_working = "${env.WORKSPACE}/doozer_working"
        buildlib.cleanWorkdir(doozer_working)

        try {
            def cmd = [
                "doozer",
                "--group", "${params.BUILD_VERSION}",
                "--assembly", "${params.ASSEMBLY}"
            ]

            if (params.DOOZER_DATA_PATH) {
                cmd += ["--data-path", "${params.DOOZER_DATA_PATH}"]
            }

            if (params.DOOZER_DATA_GITREF) {
                cmd += ["--data-gitref", "${params.DOOZER_DATA_GITREF}"]
            }

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }

            cmd << "images:release-to-base-repo" << "--nvr" << env.BASE_IMAGE_RELEASE_NVR

            echo "Will run: ${cmd.join(' ')}"

            dir(doozer_working) {
                withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                    file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    file(credentialsId: 'konflux-bot-0-ocp-art-tenant-sa', variable: 'KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-oadp-tenant-sa', variable: 'OADP_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-mtc-tenant-sa', variable: 'MTC_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-mta-tenant-sa', variable: 'MTA_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-logging-tenant-sa', variable: 'LOGGING_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-acm-tenant-sa', variable: 'ACM_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'konflux-bot-0-art-oap-tenant-sa', variable: 'OAP_KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                    usernamePassword(
                        credentialsId: 'art-dash-db-login',
                        passwordVariable: 'DOOZER_DB_PASSWORD',
                        usernameVariable: 'DOOZER_DB_USER'
                    ),
                ]) {
                    withEnv(['DOOZER_DB_NAME=art_dash', "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }

        } catch (err) {
            commonlib.email(
                    to: "aos-art-automation+failed-base-image-release@redhat.com",
                    from: "aos-art-automation@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "Error during base-image-release (NVR: ${env.BASE_IMAGE_RELEASE_NVR})",
                    body: """
There was an issue releasing a base image:

    NVR: ${env.BASE_IMAGE_RELEASE_NVR}
    Error: ${err}

Build URL: ${BUILD_URL}
""")
            throw (err)
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
