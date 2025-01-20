import java.text.SimpleDateFormat

node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("scan-for-kernel-bugs", """
            <h2>This job scans for kernel bugs, clones them into OCP Jira, and moves their statuses.</h2>
            <b>Timing</b>: Usually triggered by timer
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: '15',
                        artifactNumToKeepStr: "",
                        daysToKeepStr: '15',
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.ocpVersionParam('VERSION'),
                        commonlib.artToolsParam(),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "RECONCILE",
                            description: "Update summary, description, etc for already cloned Jira bugs",
                            defaultValue: false
                        ),
                        string(
                            name: 'TRACKERS',
                            description: '(Optional) List of KMAINT trackers to scan',
                            defaultValue: "",
                            trim: true,
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
            stage("scan-for-kernel-bugs") {
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
                    "scan-for-kernel-bugs",
                    "--group", "openshift-${params.VERSION}",
                ]
                if (params.DOOZER_DATA_PATH) {
                    cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                }
                if (params.RECONCILE) {
                    cmd << "--reconcile"
                }
                if (params.TRACKERS) {
                    for (tracker in commonlib.parseList(params.TRACKERS)) {
                        cmd << "--tracker=${tracker.trim()}"
                    }
                }
                withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'), string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                    echo "Will run ${cmd}"
                    commonlib.shell(script: cmd.join(' '))
                }
            }
        } catch (err) {
            currentBuild.result = "FAILURE"
            throw err
        } finally {
            commonlib.safeArchiveArtifacts(["artcd_working/*.log"])
            buildlib.cleanWorkspace()
        }
    }
}
