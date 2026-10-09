timeout(activity: true, time: 60, unit: 'MINUTES') {
    node() {
        timestamps {
            checkout scm
            def buildlib = load("pipeline-scripts/buildlib.groovy")
            def commonlib = buildlib.commonlib

            properties(
                [
                    disableConcurrentBuilds(),
                    buildDiscarder(logRotator(daysToKeepStr: '30')),
                    [
                        $class : 'ParametersDefinitionProperty',
                        parameterDefinitions: [
                            commonlib.artToolsParam(),
                            string(
                                name: 'GROUPS',
                                description: 'Comma-separated layered-product groups to scan',
                                defaultValue: "oadp-1.5",
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
                                name: 'ASSEMBLY',
                                description: 'Assembly name',
                                defaultValue: "stream",
                                trim: true,
                            ),
                            booleanParam(
                                name: 'DRY_RUN',
                                description: 'Run the health report without changing external state',
                                defaultValue: false,
                            ),
                            commonlib.mockParam(),
                        ],
                    ],
                ]
            )

            commonlib.checkMock()

            // Working dirs
            def artcd_working = "${WORKSPACE}/artcd_working"
            buildlib.cleanWorkdir(artcd_working)

            // Run pyartcd
            sh "mkdir -p ./artcd_working"

            def cmd = [
                "artcd",
                "-v",
                "--working-dir=${artcd_working}",
                "--config=./config/artcd.toml",
            ]
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "layered-products-image-health",
                "--groups=${commonlib.cleanCommaList(params.GROUPS)}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.DOOZER_DATA_PATH) {
                cmd << "--data-path=${params.DOOZER_DATA_PATH}"
            }
            if (params.DOOZER_DATA_GITREF) {
                cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
            }

            withCredentials([
                string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
            ]) {
                wrap([$class: 'BuildUser']) {
                    builderEmail = env.BUILD_USER_EMAIL
                }

                withEnv([
                    "BUILD_USER_EMAIL=${builderEmail ?: ''}",
                    "BUILD_URL=${BUILD_URL}",
                    "JOB_NAME=${JOB_NAME}",
                ]) {
                    try {
                        echo "Will run ${cmd.join(' ')}"
                        commonlib.shell(script: cmd.join(' '))
                    } finally {
                        commonlib.safeArchiveArtifacts([
                            "artcd_working/**/*.log",
                        ])
                        buildlib.cleanWorkspace()
                    }
                }
            }
        }
    }
}
