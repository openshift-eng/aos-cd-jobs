node() {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    properties(
        [
            disableConcurrentBuilds(),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.artToolsParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION'),
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
                        description: '(Optional) Comma/space-separated list to include/exclude per IMAGE_BUILD_STRATEGY (e.g. logging-kibana5,openshift-jenkins-2)',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'SEND_TO_RELEASE_CHANNEL',
                        defaultValue: true,
                        description: "If true, send output to #art-release-4-<version>"
                    ),
                    booleanParam(
                        name: 'SEND_TO_FORUM_OCP_ART',
                        defaultValue: false,
                        description: "If true, send notification to #forum-ocp-art"
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    currentBuild.displayName += " - ${params.BUILD_VERSION}"

    // Working dirs
    def artcd_working = "${WORKSPACE}/artcd_working"
    def doozer_working = "${artcd_working}/doozer_working"
    buildlib.cleanWorkdir(artcd_working)

    // Run pyartcd
    sh "mkdir -p ./artcd_working"

    def cmd = [
        "artcd",
        "-v",
        "--working-dir=${artcd_working}",
        "--config=./config/artcd.toml",
        "images-health",
        "--version=${params.BUILD_VERSION}"
    ]
    if (params.DOOZER_DATA_PATH) {
        cmd << "--data-path=${params.DOOZER_DATA_PATH}"
    }
    if (params.DOOZER_DATA_GITREF) {
        cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
    }
    if (params.IMAGE_LIST) {
        cmd << "--image-list=${params.IMAGE_LIST}"
    }
    if (params.SEND_TO_RELEASE_CHANNEL) {
        cmd << "--send-to-release-channel"
    }
    if (params.SEND_TO_FORUM_OCP_ART) {
        cmd << "--send-to-forum-ocp-art"
    }

    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                     string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                     usernamePassword(credentialsId: 'art-dash-db-login', passwordVariable: 'DOOZER_DB_PASSWORD', usernameVariable: 'DOOZER_DB_USER'),
                     file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {

        wrap([$class: 'BuildUser']) {
            builderEmail = env.BUILD_USER_EMAIL
        }

        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "DOOZER_DB_NAME=art_dash"]) {
            try {
                echo "Will run ${cmd.join(' ')}"
                commonlib.shell(script: cmd.join(' '))
            } catch (exception) {
                slacklib.to(BUILD_VERSION).say(":alert: Image health check job failed!\n${BUILD_URL}")
                currentBuild.result = "FAILURE"
                throw exception  // gets us a stack trace FWIW
            } finally {
                commonlib.safeArchiveArtifacts([
                    "artcd_working/**/*.log",
                ])
            }
        }
    }
}
