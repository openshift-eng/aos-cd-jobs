node() {
    checkout scm
    def buildlib = load('pipeline-scripts/buildlib.groovy')
    def commonlib = buildlib.commonlib
    commonlib.describeJob("fbc-import-from-index", """
        <h2>Import FBC catalog objects into ART's FBC repo from an existing operator catalog image</h2>
    """)

    properties([
        disableResume(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                    name: 'ART_TOOLS_COMMIT',
                    description: 'Override the art-tools submodule; Format is ghuser@commitish e.g. jupierce@covscan-to-podman-2',
                    defaultValue: "",
                    trim: true
                ),
                choice(
                    name: 'BUILD_VERSION',
                    choices: commonlib.ocpVersions,
                    description: 'OCP Version',
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
                string(
                    name: 'FROM_OPERATOR_INDEX',
                    description: '(Optional) The operator index image to import from. Default is the latest production index image for this OCP version.',
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: 'INTO_FBC_REPO',
                    description: '(Optional) The FBC repo to import into. Default is https://github.com/openshift-priv/art-fbc.git',
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
            ], // parameterDefinitions
        ], // ParametersDefinitionProperty
    ]) // properties

    commonlib.checkMock()

    def operator_nvrs = []
    def only = []
    def exclude = []

    stage('Set build info') {
        operator_nvrs = commonlib.parseList(params.OPERATOR_NVRS)
        only = commonlib.parseList(params.ONLY)
        exclude = commonlib.parseList(params.EXCLUDE)
        currentBuild.displayName += " (${params.BUILD_VERSION})"

        if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
            currentBuild.displayName += " - assembly ${params.ASSEMBLY}"
        }
    }

    stage('Import FBC catalog objects') {
        script {
            // Prepare working dirs
            buildlib.init_artcd_working_dir()
            def doozer_working = "${WORKSPACE}/doozer_working"
            buildlib.cleanWorkdir(doozer_working)

            // Create artcd command
            withCredentials([
                string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                string(credentialsId: 'konflux-art-images-username', variable: 'KONFLUX_ART_IMAGES_USERNAME'),
                string(credentialsId: 'konflux-art-images-password', variable: 'KONFLUX_ART_IMAGES_PASSWORD'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                file(credentialsId: 'creds_registry.redhat.io', variable: 'KONFLUX_OPERATOR_INDEX_AUTH_FILE'),
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
                    "fbc-import-from-index",
                    "--version=${params.BUILD_VERSION}",
                    "--assembly=${params.ASSEMBLY}",
                    "--data-path=${params.DOOZER_DATA_PATH}",
                    "--data-gitref=${params.DOOZER_DATA_GITREF}",
                ]
                if (only)
                    cmd << "--only=${only.join(',')}"
                if (exclude)
                    cmd << "--exclude=${exclude.join(',')}"
                if (params.FROM_OPERATOR_INDEX)
                    cmd << "--from-operator-index=${params.FROM_OPERATOR_INDEX}"
                if (params.INTO_FBC_REPO)
                    cmd << "--into-fbc-repo=${params.INTO_FBC_REPO}"

                // Run pipeline
                timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                    echo "Will run ${cmd.join(' ')}"
                    withEnv(["BUILD_URL=${env.BUILD_URL}"]) {
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            throw err
                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                                "artcd_working/**/*.yaml",
                            ])
                        }
                    } // withEnv
                } // timeout
            } // withCredentials
        } // script
    } //stage
} // node
