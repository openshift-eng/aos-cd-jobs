node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("tag-rpms", """
            <h2>This job will check rpms in configured Brew tags then tag them into target Brew tags.</h2>
            <p>This is mainly to support weekly kernel release via OCP</p>
            <p>If you untag a build from a target Brew tag, it will not be tagged by this job anymore.</p>
            <b>Timing</b>: Usually triggered by timer
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "",
                        artifactNumToKeepStr: "",
                        daysToKeepStr: "",
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.artToolsParam(),
                        commonlib.ocpVersionParam('VERSION'),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        string(
                            name: 'DOOZER_DATA_PATH',
                            description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                            trim: true,
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )   // Please update README.md if modifying parameter names or semantics

        commonlib.checkMock()
        stage("initialize") {
            currentBuild.displayName += " $params.VERSION"
        }
        try {
            stage("tag-rpms") {
                sh "mkdir -p ./artcd_working"
                def cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=./artcd_working",
                    "--config", "./config/artcd.toml",
                ]
                if (params.DRY_RUN) {
                    cmd << "--dry-run"
                }
                cmd += [
                    "tag-rpms",
                    "--group", "openshift-${params.VERSION}",
                ]
                if (params.DOOZER_DATA_PATH) {
                    cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                }
                withCredentials([
                        string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                        string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                        string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                        string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                        string(credentialsId: 'redis-port', variable: 'REDIS_PORT'),
                    ]) {
                    echo "Will run ${cmd}"
                    withEnv(["BUILD_URL=${BUILD_URL}"]) {
                        commonlib.shell(script: cmd.join(' '))
                    }
                }
            }
        } catch (err) {
            currentBuild.result = "FAILURE"
            throw err
        } finally {
            commonlib.safeArchiveArtifacts([
                "artcd_working/doozer_working/*.log",
                "artcd_working/doozer_working/*.yaml",
                "artcd_working/doozer_working/*.yml"
            ])
            buildlib.cleanWorkspace()
        }
    }
}
