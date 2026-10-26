timeout(activity: true, time: 120, unit: 'MINUTES') {
    node() {
        timestamps {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        def artcd_working = "${WORKSPACE}/artcd_working"
        def doozer_working = "${artcd_working}/doozer_working"

        // Expose properties for a parameterized build
        properties(
            [
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: '20',
                        daysToKeepStr: '20'
                    )
                ),
                [
                    $class: 'ParametersDefinitionProperty',
                    parameterDefinitions: [
                        commonlib.artToolsParam(),
                        commonlib.ocpVersionParam('VERSION', '4plus'),
                        string(
                            name: 'ASSEMBLY',
                            description: 'Assembly to use (default: stream)',
                            defaultValue: "stream",
                            trim: true,
                        ),
                        string(
                            name: 'DATA_PATH',
                            description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                            trim: true,
                        ),
                        string(
                            name: 'DATA_GITREF',
                            description: '(Optional) Data path git [branch / tag / sha] to use',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'ONLY_STREAM',
                            description: '(Optional) Only process the specified stream name from streams.yml',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'IMAGES',
                            description: '(Optional) Comma-separated distgit keys to process (e.g. ci-openshift-base.rhel10). Must have ci_alignment.upstream_image set.',
                            defaultValue: "",
                            trim: true,
                        ),
                        booleanParam(
                            name: 'DRY_RUN',
                            description: 'Run in dry-run mode (passes --dry-run to doozer subcommands)',
                            defaultValue: false,
                        ),
                        commonlib.mockParam(),
                    ]
                ],
                disableResume()
            ]
        )

        commonlib.checkMock()

        stage("Initialize") {
            currentBuild.displayName = "#${currentBuild.number}"

            if (params.DRY_RUN) {
                currentBuild.displayName += " [DRY_RUN]"
            }

            currentBuild.description = "Assembly: ${params.ASSEMBLY}"
        }

        stage("Sync CI BuildConfigs") {
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
                "sync-ci-buildconfigs",
                "--for-release=${params.VERSION}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.DATA_PATH) {
                cmd << "--data-path=${params.DATA_PATH}"
            }
            if (params.DATA_GITREF) {
                cmd << "--data-gitref=${params.DATA_GITREF}"
            }
            if (params.ONLY_STREAM) {
                cmd << "--only-stream=${params.ONLY_STREAM}"
            }
            if (params.IMAGES) {
                cmd << "--images=${params.IMAGES}"
            }

            // Checkout optional art-tools commit override
            buildlib.initialize()

            // Run pipeline with the app.ci identity used by QCI-APPCI
            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                        string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                        string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                        string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                        string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                        file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                        file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                        file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                        usernamePassword(credentialsId: 'art_to_ci_promotion_robot--qci', usernameVariable: 'QCI_USER', passwordVariable: 'QCI_PASSWORD'),
                ]) {
                    wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                    }

                    withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        try {
                            echo "Will run ${cmd.join(' ')}"

                            timeout(activity: true, time: 120, unit: 'MINUTES') {
                                def rc = sh(script: cmd.join(' '), returnStatus: true)
                                if (rc != 0) {
                                    error("sync-ci-buildconfigs failed with exit code ${rc}")
                                }
                            }

                        } catch (err) {
                            echo "Error running ${params.VERSION} sync-ci-buildconfigs:\n${err}"
                            throw err

                        } finally {
                            // Archive logs if they exist
                            def debugLog = "${doozer_working}/debug.log"
                            if (fileExists(debugLog)) {
                                sh "mv ${debugLog} ${doozer_working}/debug-${params.VERSION}.log"
                                sh "bzip2 ${doozer_working}/debug-${params.VERSION}.log"
                                commonlib.safeArchiveArtifacts(["artcd_working/doozer_working/*.bz2"])
                            }
                            buildlib.cleanWorkspace()
                        }
                    } // withEnv
                } // withCredentials
            } // withAppCiAsArtPublish
        } // stage
        }
    }
}
