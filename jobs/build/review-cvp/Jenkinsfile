node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("review-cvp", """
            <h2>Review CVP test results</h2>
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
                        commonlib.ocpVersionParam('VERSION'),
                        string(
                            name: "ASSEMBLY",
                            description: "The name of an assembly; must be defined in releases.yml (e.g. 4.9.1)",
                            defaultValue: "stream",
                            trim: true
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Do not create auto-fix PR; just echo what the job would have done.",
                            defaultValue: false
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )   // Please update README.md if modifying parameter names or semantics

        commonlib.checkMock()
        stage("initialize") {
            buildlib.initialize()
            // buildlib.registry_quay_dev_login()
            currentBuild.displayName += " - $params.VERSION - $params.ASSEMBLY"
        }
        stage("review-cvp") {
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
                "review-cvp",
                "--group", "openshift-${params.VERSION}",
                "--assembly", params.ASSEMBLY,
            ]
            try {
                sshagent(["openshift-bot"]) {
                    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'), string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN')]) {
                        echo "Will run ${cmd}"
                        commonlib.shell(script: cmd.join(' '))
                    }
                }
            } finally {
                commonlib.safeArchiveArtifacts([
                    "artcd_working/email/**",
                    "artcd_working/**/*.json",
                    "artcd_working/**/*.log",
                    "artcd_working/**/*.yaml",
                    "artcd_working/**/*.yml",
                ])
            }
        }
    }
}
