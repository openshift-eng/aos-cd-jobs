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
                    string(
                        name: 'FIXED_CVES',
                        description: 'CVEs that are confirmed to be fixed in all given golang nvrs (comma separated). This will be used to fetch relevant Tracker bugs and move them to ON_QA state if determined to be fixed (nightly is found containing fixed builds)',
                    ),
                    booleanParam(
                        name: 'FORCE_UPDATE_TRACKERS',
                        description: 'Force update found tracker bugs for the given CVEs, even if the latest nightly is not found containing fixed builds',
                    ),
                    booleanParam(
                        name: 'SCRATCH',
                        description: 'Perform a scratch build (will not use an NVR or update tags)',
                    ),
                    booleanParam(
                        name: 'TAG_BUILD',
                        description: 'Tag builds into override tag if they are not tagged',
                    ),
                    string(
                        name: 'ART_JIRA',
                        description: 'ART jira ticket number to be used for reference when creating tickets/PRs',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'FORCE_IMAGE_BUILD',
                        description: 'Do not check if there is already a golang builder image with the rpm, but build a new one anyway',
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
            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
            file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
            string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
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
                    if (params.FIXED_CVES) {
                        cmd << "--cves=${params.FIXED_CVES}"
                    }
                    if (params.SCRATCH) {
                        cmd << "--scratch"
                    }
                    if (params.FORCE_UPDATE_TRACKERS) {
                        cmd << "--force-update-tracker"
                    }
                    if (params.TAG_BUILD) {
                        cmd << "--tag-builds"
                    }
                    if (!params.DRY_RUN) {
                        cmd << "--confirm"
                    }
                    if (params.FORCE_IMAGE_BUILD) {
                        cmd << "--force-image-build"
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
