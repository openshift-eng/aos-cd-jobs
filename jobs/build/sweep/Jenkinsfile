#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("sweep", """
        <h2>Sweep bugs</h2>
        <b>Timing</b>: This runs after component builds (ocp3/ocp4/custom jobs),
        or when preparing a nightly for examination by QE.

        After component builds, bugs are queried that are in MODIFIED state,
        and are set to ON_QA. This is the signal to QE that they can test the bug.
        In this mode of operation, ATTACH_BUGS is false.

        When preparing a set of nightlies and advisories for QE, the sweep job will
        look for all bugs that are in MODIFIED, ON_QA or VERIFIED state, and attach them
        to the default advisories, according to those recorded in ocp-build-data
        group.yml.
        For 3.11, all bugs are swept into the rpm advisory.
        For 4.y, bugs are swept into the image or extras advisory.
    """)


    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '90'
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    booleanParam(
                        name: 'ATTACH_BUGS',
                        defaultValue: false,
                        description: [
                          'If <b>on</b>: Attach MODIFIED, ON_QA, and VERIFIED bugs to their advisories',
                          'If <b>off</b>: Set MODIFIED bugs to ON_QA. Do not change advisories',
                        ].join('\n')
                    ),
                    commonlib.jiraModeParam('USEJIRA'),
                    string(
                        name: "SLACK_CHANNEL",
                        description: 'Slack channel to be notified in case of failures. ' +
                                    'Example: #art-automation-debug ' +
                                    'Leave blank to notify <strong>#art-release-<BUILD_VERSION></strong>',
                        trim: true,
                    ),
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                ],
            ],
        ]
    )

    // Check for mock build
    commonlib.checkMock()

    // Init
    echo "Initializing bug sweep for ${params.BUILD_VERSION}. Sync: #${currentBuild.number}"
    currentBuild.displayName = "${params.BUILD_VERSION}"

    // Clean workspace
    sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"

    // Sweep bugs
    stage("Sweep bugs") {
        currentBuild.description = "Sweeping new bugs<br/>"

        def cmd = [
            "artcd",
            "-vvv",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml"
        ]

        if (params.DRY_RUN) {
            cmd << "--dry-run"
        }

        cmd << "sweep-bugs" << "--version=${params.BUILD_VERSION}"

        if (params.ATTACH_BUGS) {
            cmd << "--attach-bugs"
        }

        echo "Running command: ${cmd}"

        // Execute script
        def env = []
        if (params.JIRA_MODE) {
            env << "${params.JIRA_MODE}=True"
        }
        withEnv(env) {
            withCredentials([string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                exitCode = commonlib.shell(script: cmd.join(' '), returnStatus: true)
            }
        }
        echo("command ${cmd} returned with status ${exitCode}")

        /* Handle exit code, defined as:
            0 = SUCCESS
            1 = RUNTIME_ERROR
            2 = BUILD_NOT_PERMITTED
            3 = DRY_RUN
        */
        if (exitCode == 0) {
            currentBuild.displayName += " - bug sweep"
            currentBuild.result = 'SUCCESS'
            if (params.ATTACH_BUGS) {
                channel = params.SLACK_CHANNEL.isEmpty() ? params.BUILD_VERSION : params.SLACK_CHANNEL
                slacklib.to(channel).say("""
                    :warning: @release-artists note: the sweep job was used to sweep *bugs* into advisories.
                    buildvm job: ${commonlib.buildURL('console')}
                """)
            }
        }
        if (exitCode == 1) {
            currentBuild.result = 'FAILURE'
            currentBuild.displayName += ' - runtime error'
            echo('Runtime errors were raised during the build. Check the logs for details')
        }
        if (exitCode == 2) {
            currentBuild.displayName += ' - automation frozen'
            currentBuild.result = 'UNSTABLE'
            currentBuild.description = 'Builds not permitted'
            echo('This build did not run as it is not permitted according to current group.yml')
        }
        if (exitCode == 3) {
            currentBuild.displayName += " - dry run"
            echo('This build was run in dry run mode')
        }
    }
}
