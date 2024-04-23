#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("rebuild-golang-rpms", """
        <h2>Rebuild non-ART golang rpms in ART candidate tags</h2>
    """)

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
                        description: 'Golang NVRs (one or multiple but atmost one for a rhel version) you want to build rpms for (comma/space separated)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ART_JIRA',
                        description: 'ART jira ticket number as reference - this will be included in the commit message when bumping and building rpms',
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
            error("You must provide golang NVR(s) rpms are supposed to be built against")
        }

        if (!params.ART_JIRA) {
            error("You must provide an ART jira ticket id for reference")
        }

        def dry_run = params.DRY_RUN ? '[DRY_RUN]' : ''
        currentBuild.displayName = "${params.BUILD_VERSION} ${dry_run}"
    }

    stage('Rebuild golang rpms') {
        def golang_nvrs = commonlib.cleanSpaceList(params.GOLANG_NVRS)

        script {
            // Prepare working dir
            sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"

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
                "rebuild-golang-rpms",
                "--ocp-version=${params.BUILD_VERSION}",
                "--art-jira=${params.ART_JIRA}",
                "${golang_nvrs}"
            ]

            // Run pipeline
            timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                echo "Will run ${cmd.join(' ')}"
                withCredentials([
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                        ]) {
                    withEnv(["BUILD_URL=${env.BUILD_URL}"]) {
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            throw err
                        }
                    } // withEnv
                } // withCredentials
            } // timeout
        }
    }

    stage('Clean up') {
        buildlib.cleanWorkspace()
    }
}
