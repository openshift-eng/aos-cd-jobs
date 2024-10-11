#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("golang-builder", """
        <h2>Build and update golang-builder images</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.
    """)

    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: 'BUILD_VERSION',
                        choices: commonlib.ocpVersions,
                        description: 'OCP Version',
                    ),
                    string(
                        name: 'GOLANG_NVRS',
                        description: 'Golang NVRs (one or multiple but atmost one for a rhel version) that you expect to build images for. This is to ensure that the right compiler nvrs are picked up (comma/space separated)',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'CREATE_TAGGING_TICKET',
                        description: 'Create a CWFCONF Jira ticket for tagging golang builds in ART buildroots',
                    ),
                    booleanParam(
                        name: 'SCRATCH',
                        description: 'Perform a scratch build (will not use an NVR or update tags)',
                    ),
                    string(
                        name: 'ART_JIRA',
                        description: 'ART jira ticket number to be used for reference when creating tickets/PRs',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.mockParam(),
                    commonlib.dryrunParam(),
                    commonlib.artToolsParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    stage('Validate Parameters') {
        if (!params.GOLANG_NVRS) {
            error("You must provide golang NVR(s) that you expect to build images for. This is to ensure that the right compiler nvrs are picked up")
        }

        if (!params.ART_JIRA) {
            error("You must provide an ART jira ticket id for reference.")
        }
    }

    stage('Build golang-builder images') {
        def golang_nvrs = commonlib.cleanSpaceList(params.GOLANG_NVRS)
        withCredentials([
            string(credentialsId: 'gitlab-ocp-release-schedule-schedule', variable: 'GITLAB_TOKEN'),
            string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
            string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
            string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN',
            file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'))
        ]) {
            withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']) {
                script {
                    // Prepare working dir
                    buildlib.init_artcd_working_dir()

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
                        "update-golang",
                        "--ocp-version=${params.BUILD_VERSION}",
                        "--art-jira=${params.ART_JIRA}",
                        "${golang_nvrs}"
                    ]
                    if (params.CREATE_TAGGING_TICKET) {
                        cmd << "--create-tagging-ticket"
                    }
                    if (params.SCRATCH) {
                        cmd << "--scratch"
                    }
                    if (!params.DRY_RUN) {
                        cmd << "--confirm"
                    }

                    // Run pipeline
                    timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                        echo "Will run ${cmd.join(' ')}"
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            throw err
                        }
                    } // timeout

                    commonlib.safeArchiveArtifacts([
                        "artcd_working/**/*.json",
                        "artcd_working/**/*.log",
                        "artcd_working/**/*.yaml",
                        "artcd_working/**/*.yml",
                    ])
                }
            }
        }
    }

    stage('Clean up') {
        buildlib.cleanWorkspace()
    }
}
