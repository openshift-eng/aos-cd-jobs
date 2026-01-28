node() {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    properties(
        [
            buildDiscarder(logRotator(daysToKeepStr: '30')),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.artToolsParam(),
                    string(
                        name: 'GROUP',
                        description: 'OCP group to scan (e.g. openshift-4.17)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'DATA_PATH',
                        description: '(Optional) ocp-build-data fork to use',
                        defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Assembly to scan',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    string(
                        name: 'REPOS',
                        description: '(Optional) Comma-separated list of repos to check. If empty, scan all repos.',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    if (!params.GROUP) {
        currentBuild.result = 'ABORTED'
        error('GROUP parameter is required')
    }

    // Set friendly build name
    currentBuild.displayName = "#${currentBuild.number} ${params.GROUP}/${params.ASSEMBLY}"
    if (params.DRY_RUN) {
        currentBuild.displayName += " [DRY_RUN]"
    }

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

    cmd << "scan-plashet-rpms"
    cmd << "--group=${params.GROUP}"

    if (params.DATA_PATH) {
        cmd << "--data-path=${params.DATA_PATH}"
    }
    if (params.DATA_GITREF) {
        cmd << "--data-gitref=${params.DATA_GITREF}"
    }
    if (params.ASSEMBLY) {
        cmd << "--assembly=${params.ASSEMBLY}"
    }
    if (params.REPOS) {
        // Split comma-separated repos and add each as --repos argument
        def repos = commonlib.cleanCommaList(params.REPOS).split(',')
        repos.each { repo ->
            cmd << "--repos=${repo.trim()}"
        }
    }

    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                     string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                     string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                     string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                     string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD')]) {

        wrap([$class: 'BuildUser']) {
            builderEmail = env.BUILD_USER_EMAIL
        }

        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}"]) {
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
