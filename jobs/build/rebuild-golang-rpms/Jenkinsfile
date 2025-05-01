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
                        name: 'FIXED_CVES',
                        description: 'CVEs that are confirmed to be fixed in all given golang nvrs (comma separated). This will be used to fetch relevant Tracker bugs and move them to ON_QA state if determined to be fixed (fixed builds are found)',
                    ),
                    string(
                        name: 'ART_JIRA',
                        description: 'ART jira ticket number as reference - this will be included in the commit message when bumping and building rpms',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'RPMS',
                        description: '(Optional) Only consider these rpms. Comma separated list of rpms to rebuild',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'FORCE_REBUILD',
                        defaultValue: false,
                        description: 'Force rebuild even if the rpm is already on given golang',
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
                "rebuild-golang-rpms",
                "--ocp-version=${params.BUILD_VERSION}",
                "--art-jira=${params.ART_JIRA}",
                "${golang_nvrs}"
            ]
            if (params.RPMS) {
                cmd << "--rpms=${params.RPMS}"
            }
            if (params.FIXED_CVES) {
                cmd << "--cves=${params.FIXED_CVES}"
            }
            if (params.FORCE_REBUILD) {
                cmd << "--force"
            }

            // Run pipeline
            timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                echo "Will run ${cmd.join(' ')}"
                withCredentials([
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                            string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                        ]) {
                    withEnv(["BUILD_URL=${env.BUILD_URL}"]) {
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            throw err
                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                            ])
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
