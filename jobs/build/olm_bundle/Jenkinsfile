node('covscan') {
    checkout scm
    buildlib = load('pipeline-scripts/buildlib.groovy')
    commonlib = buildlib.commonlib
    commonlib.describeJob("olm_bundle", """
        <h2>Create bundle images for OLM operators</h2>
        <b>Timing</b>: Run by the ocp4 or custom jobs after new builds.
        Should only need humans to run if something breaks.

        This job creates operator bundle images. These are much like operator
        metadata images in that it contains an operator manifest with a CSV.
        However it only represents a single version of that operator, and only
        ever needs to be built once; there is no need to rebuild for release.
    """)
    bundle_nvrs = []
    operator_nvrs = []
    only = []
    exclude = []

    properties([
        disableResume(),
        skipDefaultCheckout(),
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
        steps {
            script {
                operator_nvrs = commonlib.parseList(params.OPERATOR_NVRS)
                only = commonlib.parseList(params.ONLY)
                exclude = commonlib.parseList(params.EXCLUDE)
                currentBuild.displayName += " (${params.BUILD_VERSION})"

                if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
                    currentBuild.displayName += " - assembly ${params.ASSEMBLY}"
                }
            }
        }
    }

    stage('Build bundles') {
        steps {
            script {
                // Prepare working dirs
                sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                def doozer_working = "${WORKSPACE}/doozer_working"
                buildlib.cleanWorkdir(doozer_working)

                // Create artcd command
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
                    "olm-bundle",
                    "--version=${params.BUILD_VERSION}",
                    "--assembly=${params.ASSEMBLY}",
                    "--data-path=${params.DOOZER_DATA_PATH}",
                    "--data-gitref=${params.DOOZER_DATA_GITREF}"
                ]
                if (operator_nvrs)
                    cmd << "--nvrs=${operator_nvrs.join(',')}"
                if (only)
                    cmd << "--only=${only.join(',')}"
                if (exclude)
                    cmd << "--exclude=${exclude.join(',')}"
                if (params.FORCE_BUILD)
                    cmd << "--force"

                // Run pipeline
                timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                    echo "Will run ${cmd}"
                    withCredentials([
                                string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                                string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                                string(credentialsId: 'redis-port', variable: 'REDIS_PORT'),
                                string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')
                            ]) {
                        withEnv(["BUILD_URL=${env.BUILD_URL}"]) {
                            try {
                                sh(script: cmd.join(' '), returnStdout: true)
                            } catch (err) {
                                throw err
                            } finally {
                                commonlib.safeArchiveArtifacts([
                                    "doozer_working/*.log",
                                    "doozer_working/*.yaml",
                                ])
                            }
                        } // withEnv
                    } // withCredentials
                } // timeout
            } // script
        } // steps
    } //stage
} // node
