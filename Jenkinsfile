node() {
    timestamps {
    checkout scm
    def buildlib = load('pipeline-scripts/buildlib.groovy')
    def commonlib = buildlib.commonlib
    commonlib.describeJob("olm_bundle_konflux", """
        <h2>Create bundle images for OLM operators</h2>
        <b>Timing</b>: Run by the ocp4-konflux job for new builds.
        Should only need humans to run if something breaks.

        This job creates operator bundle images. These are much like operator
        metadata images in that it contains an operator manifest with a CSV.
        However it only represents a single version of that operator, and only
        ever needs to be built once; there is no need to rebuild for release.
    """)
    def bundle_nvrs = []
    def operator_nvrs = []
    def only = []
    def exclude = []

    properties([
        disableResume(),
        buildDiscarder(logRotator(daysToKeepStr: '30')),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                    name: 'ART_TOOLS_COMMIT',
                    description: 'Override the art-tools submodule; Format is ghuser@commitish e.g. jupierce@covscan-to-podman-2',
                    defaultValue: "",
                    trim: true
                ),
                string(
                    name: 'BUILD_VERSION',
                    description: 'For example, 4.19 (for OCP), 1.6.3 (for OADP)',
                    trim: true,
                ),
                string(
                    name: 'GROUP',
                    description: '(Optional) The group to be used, by default it will be assumed to be openshift-<version>',
                    trim: true,
                ),
                string(
                    name: 'ASSEMBLY',
                    description: 'Assembly name.',
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
                    name: 'OPERATOR_NVRS',
                    description: '(Optional) List **only** the operator NVRs you want to build bundles for, everything else gets ignored. The operators should not be mode:disabled/wip in ocp-build-data',
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: 'ONLY',
                    description: '(Optional) List **only** the operators you want '  +
                                 'to build, everything else gets ignored.\n'         +
                                 'Format: Comma and/or space separated list of brew '+
                                 'packages (e.g.: cluster-nfd-operator-container)\n' +
                                 'Leave empty to build all (except EXCLUDE, if defined)',
                    defaultValue: '',
                    trim: true,
                ),
                string(
                    name: 'EXCLUDE',
                    description: '(Optional) List the operators you **don\'t** want ' +
                                 'to build, everything else gets built.\n'            +
                                 'Format: Comma and/or space separated list of brew ' +
                                 'packages (e.g.: cluster-nfd-operator-container)\n'  +
                                 'Leave empty to build all (or ONLY, if defined)',
                    defaultValue: '',
                    trim: true,
                ),
                booleanParam(
                    name: 'FORCE_BUILD',
                    description: 'Rebuild bundle containers, even if they already exist for given operator NVRs',
                    defaultValue: false,
                ),
                string(
                    name: 'PLR_TEMPLATE_COMMIT',
                    description: '(Optional) Override the Pipeline Run template commit from openshift-priv/art-konflux-template; Format is ghuser@commitish e.g. jupierce@covscan-to-podman-2',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name: 'DRY_RUN',
                    description: 'Just show what would happen, without actually executing the steps',
                    defaultValue: false,
                ),
                booleanParam(
                    name: 'MOCK',
                    description: 'Pick up changed job parameters and then exit',
                    defaultValue: false,
                ),
            ],
        ],
    ])

    commonlib.checkMock()
    stage('Set build info') {
        operator_nvrs = commonlib.parseList(params.OPERATOR_NVRS)
        only = commonlib.parseList(params.ONLY)
        exclude = commonlib.parseList(params.EXCLUDE)
        currentBuild.displayName += " (${params.BUILD_VERSION})"

        if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
            currentBuild.displayName += " - assembly ${params.ASSEMBLY}"
        }
    }

    stage('Build bundles') {
        script {
            // Prepare working dirs
            buildlib.init_artcd_working_dir()

            // Create artcd command
            withCredentials([
                string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                file(credentialsId: 'openshift-bot-oadp-konflux-service-account', variable: 'OADP_KONFLUX_SA_KUBECONFIG'),
                file(credentialsId: 'openshift-bot-mtc-konflux-service-account', variable: 'MTC_KONFLUX_SA_KUBECONFIG'),
                file(credentialsId: 'openshift-bot-mta-konflux-service-account', variable: 'MTA_KONFLUX_SA_KUBECONFIG'),
                file(credentialsId: 'openshift-bot-logging-konflux-service-account', variable: 'LOGGING_KONFLUX_SA_KUBECONFIG'),
                string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                file(credentialsId: 'konflux-art-images-auth-file', variable: 'KONFLUX_ART_IMAGES_AUTH_FILE'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
            ]) {
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
                    "olm-bundle-konflux",
                    "--version=${params.BUILD_VERSION}",
                    "--assembly=${params.ASSEMBLY}",
                    "--data-path=${params.DOOZER_DATA_PATH}",
                    "--data-gitref=${params.DOOZER_DATA_GITREF}",
                ]
                if (params.GROUP)
                   cmd << "--group=${params.GROUP}"
                if (operator_nvrs)
                    cmd << "--nvrs=${operator_nvrs.join(',')}"
                if (only)
                    cmd << "--only=${only.join(',')}"
                if (exclude)
                    cmd << "--exclude=${exclude.join(',')}"
                if (params.FORCE_BUILD)
                    cmd << "--force"
                if (params.PLR_TEMPLATE_COMMIT) {
                    cmd << "--plr-template=${params.PLR_TEMPLATE_COMMIT}"
                }

                // Run pipeline
                timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                    echo "Will run ${cmd.join(' ')}"
                    withEnv(["BUILD_URL=${env.BUILD_URL}"]) {
                        try {
                            // Run the command and capture exit code
                            // Exit code 2 indicates UNSTABLE (partial bundle build success)
                            def exitCode = sh(script: cmd.join(' '), returnStatus: true)
                            if (exitCode == 2) {
                                currentBuild.result = 'UNSTABLE'
                                echo "Pipeline completed with UNSTABLE status (some bundle builds failed, but FBC triggered for successful bundles)"
                            } else if (exitCode != 0) {
                                error("Pipeline failed with exit code ${exitCode}")
                            }
                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                            ])
                            buildlib.cleanWorkspace()
    }
                        }
                    } // withEnv
                } // timeout
            } // withCredentials
        } // script
    } //stage
} // node
