node {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("build-microshift", """
            <h2>Rebase and build MicroShift for an assembly.</h2>
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
                        commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                        commonlib.doozerParam(),
                        string(
                            name: "ASSEMBLY",
                            description: "The name of an assembly to rebase & build for. e.g. 4.9.1",
                            trim: true
                        ),
                        string(
                            name: 'OCP_BUILD_DATA_URL',
                            description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                            defaultValue: "https://github.com/openshift/ocp-build-data",
                            trim: true,
                        ),
                        booleanParam(
                            name: 'IGNORE_LOCKS',
                            description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            buildlib.initialize()
            if (params.DRY_RUN) {
                currentBuild.displayName += " - [DRY RUN]"
            }
            currentBuild.displayName += " - $params.ASSEMBLY"
        }

        stage("rebuild") {
            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"
            def cmd = [
                "artcd",
                "-vv",
                "--working-dir=./artcd_working",
                "--config", "./config/artcd.toml",
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "build-microshift",
                "--ocp-build-data-url", params.OCP_BUILD_DATA_URL,
                "-g", "openshift-$params.BUILD_VERSION",
                "--assembly", params.ASSEMBLY,
            ]
            withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')]) {
                echo "Will run ${cmd}"
                if (params.IGNORE_LOCKS) {
                     commonlib.shell(script: cmd.join(' '))
                } else {
                    lock("build-microshift-lock-${params.BUILD_VERSION}") { commonlib.shell(script: cmd.join(' ')) }
                }
            }
        }
        stage("save artifacts") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/email/**",
                "artcd_working/**/*.json",
                "artcd_working/**/*.log",
            ])
        }
    }
}
