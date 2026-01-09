node() {
    timestamps {
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
                        name: 'VERSIONS',
                        description: '(Optional) Comma/space-separated list of OCP version to scan. If empty, scan all versions.',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'SEND_TO_RELEASE_CHANNEL',
                        defaultValue: "#art-okd-release",
                        description: "If set, send output to the Slack channel"
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Assembly name',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

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
        "okd-images-health"
    ]
    if (params.VERSIONS) {
        cmd << "--versions=${commonlib.cleanCommaList(params.VERSIONS)}"
    }
    if (params.DOOZER_DATA_PATH) {
        cmd << "--data-path=${params.DOOZER_DATA_PATH}"
    }
    if (params.DOOZER_DATA_GITREF) {
        cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
    }
    if (params.SEND_TO_RELEASE_CHANNEL) {
        cmd << "--send-to-release-channel=${params.SEND_TO_RELEASE_CHANNEL}"
    }
    if (params.ASSEMBLY) {
        cmd << "--assembly=${params.ASSEMBLY}"
    }

    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                     string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                     string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                     usernamePassword(credentialsId: 'art-dash-db-login', passwordVariable: 'DOOZER_DB_PASSWORD', usernameVariable: 'DOOZER_DB_USER'),
                     file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {

        wrap([$class: 'BuildUser']) {
            builderEmail = env.BUILD_USER_EMAIL
        }

        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "DOOZER_DB_NAME=art_dash"]) {
            try {
                echo "Will run ${cmd.join(' ')}"
                commonlib.shell(script: cmd.join(' '))
            } finally {
                commonlib.safeArchiveArtifacts([
                    "artcd_working/**/*.log",
                ])
            }
        }
    }
    }
}
