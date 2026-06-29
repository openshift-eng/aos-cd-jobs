#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("golang-builder-shipment", """
        <h2>Create a shipment MR for golang builder images</h2>
        <b>Timing</b>: Run manually after golang builder Konflux images are built.

        Creates a shipment MR in <code>ocp-shipment-data</code> for ERT-gated
        release of golang builder images.

        Supply either:
        <ul>
          <li><b>GOLANG_NVRS</b> — golang RPM NVRs (auto-resolves Konflux image NVRs and group)</li>
          <li><b>IMAGE_NVRS</b> — explicit Konflux image NVRs (for manual override)</li>
        </ul>

        The pipeline auto-detects <code>prod</code> vs <code>ec</code> environment
        from <code>ocp-build-data</code> software_lifecycle.phase.
    """)

    properties([
        disableResume(),
        buildDiscarder(
          logRotator(
              artifactDaysToKeepStr: '30',
              daysToKeepStr: '30',
              numToKeepStr: '100',
          )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.suppressEmailParam(),
                commonlib.mockParam(),
                commonlib.ocpVersionParam('BUILD_VERSION', '4plus'),
                commonlib.artToolsParam(),
                string(
                    name: 'GOLANG_NVRS',
                    description: 'Golang RPM NVRs (e.g. golang-1.25.9-1.el9). Resolves Konflux image NVRs and group automatically.',
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: 'IMAGE_NVRS',
                    description: '(Optional) Explicit Konflux image NVRs to override auto-resolution (comma or space separated)',
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: 'ART_JIRA',
                    description: 'ART Jira ticket for reference (e.g. ART-20930)',
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
                    name: 'SHIPMENT_DATA_REPO_URL',
                    description: '(Optional) Override ocp-shipment-data repo URL',
                    defaultValue: "",
                    trim: true,
                ),
                commonlib.dryrunParam(),
            ],
        ]
    ])

    commonlib.checkMock()

    stage('Validate Parameters') {
        if (!params.GOLANG_NVRS?.trim() && !params.IMAGE_NVRS?.trim()) {
            error('Either GOLANG_NVRS or IMAGE_NVRS is required.')
        }

        echo("Golang Builder Shipment Parameters:")
        echo("  BUILD_VERSION: ${params.BUILD_VERSION}")
        echo("  GOLANG_NVRS: ${params.GOLANG_NVRS}")
        echo("  IMAGE_NVRS: ${params.IMAGE_NVRS}")
        echo("  ART_JIRA: ${params.ART_JIRA}")
        echo("  DRY_RUN: ${params.DRY_RUN}")

        currentBuild.displayName = "${params.BUILD_VERSION}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        buildlib.elliott "--version"
        buildlib.oc("version --client=true -o yaml")
    }

    stage("Create shipment MR") {
        def artcd_working = "${env.WORKSPACE}/artcd_working"
        buildlib.cleanWorkdir(artcd_working)

        try {
            withCredentials([
                string(credentialsId: 'art-bot-jenkins-gitlab', variable: 'GITLAB_TOKEN'),
                string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
            ]) {
                withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                    script {
                        buildlib.init_artcd_working_dir()

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
                            "golang-builder-shipment",
                            "--ocp-version=${params.BUILD_VERSION}",
                        ]
                        if (params.DOOZER_DATA_PATH) {
                            cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                        }
                        if (params.ART_JIRA) {
                            cmd << "--art-jira=${params.ART_JIRA}"
                        }
                        if (params.SHIPMENT_DATA_REPO_URL) {
                            cmd << "--shipment-data-repo-url=${params.SHIPMENT_DATA_REPO_URL}"
                        }

                        if (params.IMAGE_NVRS?.trim()) {
                            // Explicit Konflux image NVRs provided
                            cmd << commonlib.cleanSpaceList(params.IMAGE_NVRS)
                        } else {
                            // Auto-resolve from golang RPM NVRs
                            cmd << "--golang-nvrs=${commonlib.cleanSpaceList(params.GOLANG_NVRS)}"
                        }

                        timeout(activity: true, time: 15, unit: 'MINUTES') {
                            echo "Will run ${cmd.join(' ')}"
                            sh(script: cmd.join(' '), returnStdout: true)
                        }
                    }
                }
            }

        } catch (err) {
            commonlib.email(
                    to: "aos-art-automation+failed-golang-builder-shipment@redhat.com",
                    from: "aos-art-automation@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "Error during golang-builder-shipment",
                    body: """
There was an issue creating a golang builder shipment MR:

    BUILD_VERSION: ${params.BUILD_VERSION}
    GOLANG_NVRS: ${params.GOLANG_NVRS}
    IMAGE_NVRS: ${params.IMAGE_NVRS}
    Error: ${err}

Build URL: ${BUILD_URL}
""")
            throw (err)
        } finally {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.json",
                "artcd_working/**/*.log",
                "artcd_working/**/*.yaml",
                "artcd_working/**/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }

    }
}
