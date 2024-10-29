// activity == true, means that the timeout will only occur if there
// is no log activity for the specified period.
timeout(activity: true, time: 60, unit: 'MINUTES') {
    node() {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib
        def doozer_working = "${WORKSPACE}/doozer_working"

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
                        commonlib.ocpVersionParam('VERSION', '4'),
                        string(
                            name: 'ASSEMBLY',
                            description: 'Assembly to be scanned',
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
                        name: 'IMAGE_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_IMAGES (e.g. logging-kibana5,openshift-jenkins-2)',
                        defaultValue: "",
                        trim: true,
                    ),
                        booleanParam(
                            name: 'DRY_RUN',
                            description: 'Run scan without triggering subsequent jobs',
                            defaultValue: false,
                        ),
                        commonlib.mockParam(),
                    ]
                ],
                disableResume()
            ]
        )

        commonlib.checkMock()

        retry(3) {
            buildlib.registry_quay_dev_login()
        }

        stage("Initialize") {
            currentBuild.displayName = "#${currentBuild.number} ${params.VERSION}"

            if (params.DRY_RUN) {
                currentBuild.displayName += " [DRY_RUN]"
            }
        }

        stage("Scan") {
            sshagent(["openshift-bot"]) {
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
                    "beta:konflux:ocp4-scan",
                    "--version=${params.VERSION}",
                    "--assembly=${params.ASSEMBLY}",
                ]
                if (params.DOOZER_DATA_PATH) {
                    cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                }
                if (params.DOOZER_DATA_GITREF) {
                    cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
                }
                if (params.IMAGE_LIST) {
                    cmd << "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}"
                }

                // Run pipeline
                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                            string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                            string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                            string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                            file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS')
                        ]) {
                        // There is a vanishingly small race condition here, but it is not dangerous;
                        // it can only lead to undesired delays (i.e. waiting to scan while a build is ongoing).
                        wrap([$class: 'BuildUser']) {
                            builderEmail = env.BUILD_USER_EMAIL
                        }

                        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                            try {
                                echo "Will run ${cmd}"

                                timeout(activity: true, time: 60, unit: 'MINUTES') {
                                    sh(script: cmd.join(' '))
                                }

                            } catch (err) {
                                echo "Error running ${params.VERSION} scan:\n${err}"
                                throw err

                            } finally {
                                // If scan was skipped, there won't be any logs to archive
                                if (fileExists(doozer_working)) {
                                    sh "mv ${doozer_working}/debug.log ${doozer_working}/debug-${params.VERSION}.log"
                                    sh "bzip2 ${doozer_working}/debug-${params.VERSION}.log"
                                    commonlib.safeArchiveArtifacts(["artcd_working/doozer_working/*.bz2"])
                                }
                                buildlib.cleanWorkspace()
                            }
                        } // withEnv
                    } // withCredentials
                } // withAppCiAsArtPublish
            } // sshagent
        } // stage
    }
}
