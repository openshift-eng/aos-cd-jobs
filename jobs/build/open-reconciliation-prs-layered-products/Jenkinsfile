// activity == true, means that the timeout will only occur if there
// is no log activity for the specified period.
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
                        choice(
                            name: 'GROUP',
                            description: 'Layered product group to reconcile',
                            choices: commonlib.nonOCPGroups,
                        ),
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
                            name: 'ADD_LABELS',
                            description: '(Optional) Space-delimited labels to add to reconciliation PRs',
                            defaultValue: "",
                            trim: true,
                        ),
                        booleanParam(
                            name: 'DRY_RUN',
                            description: 'Run in dry-run mode (passes --moist-run to doozer PR operations)',
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

        stage("Open Reconciliation PRs (Layered)") {
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
                "open-reconciliation-prs-layered",
                "--group=${params.GROUP}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.DATA_PATH) {
                cmd << "--data-path=${params.DATA_PATH}"
            }
            if (params.DATA_GITREF) {
                cmd << "--data-gitref=${params.DATA_GITREF}"
            }
            if (params.ADD_LABELS) {
                cmd << "--add-labels=${params.ADD_LABELS}"
            }
            if (params.DRY_RUN) {
                cmd << "--moist-run"
            }

            // Checkout optional art-tools commit override
            buildlib.initialize()

            // Run pipeline
            withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                    file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                ]) {
                wrap([$class: 'BuildUser']) {
                    builderEmail = env.BUILD_USER_EMAIL
                }

                withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                    try {
                        echo "Will run ${cmd.join(' ')}"

                        timeout(activity: true, time: 120, unit: 'MINUTES') {
                            def rc = sh(script: cmd.join(' '), returnStatus: true)
                            if (rc == 25) {
                                currentBuild.result = 'UNSTABLE'
                                echo "open-reconciliation-prs-layered completed with partial errors (rc=25)"
                            } else if (rc != 0) {
                                error("open-reconciliation-prs-layered failed with exit code ${rc}")
                            }
                        }

                    } catch (err) {
                        echo "Error running ${params.GROUP} open-reconciliation-prs-layered:\n${err}"
                        throw err

                    } finally {
                        // Archive logs if they exist
                        def debugLog = "${doozer_working}/debug.log"
                        if (fileExists(debugLog)) {
                            sh "mv ${debugLog} ${doozer_working}/debug-${params.GROUP}.log"
                            sh "bzip2 ${doozer_working}/debug-${params.GROUP}.log"
                            commonlib.safeArchiveArtifacts(["artcd_working/doozer_working/*.bz2"])
                        }
                        buildlib.cleanWorkspace()
                    }
                } // withEnv
            } // withCredentials
        } // stage
        }
    }
}
