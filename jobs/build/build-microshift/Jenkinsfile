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
                            defaultValue: "test",
                            trim: true
                        ),
                        string(
                            name: 'RELEASE_PAYLOADS',
                            description: '(Optional) List of release payloads to rebase against; can be nightly names or full pullspecs',
                            defaultValue: "",
                            trim: true,
                        ),
                        booleanParam(
                            name: "UPDATE_POCKET",
                            description: "Update pocket on mirror; ",
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "NO_REBASE",
                            description: "(For testing only) Do not rebase microshift code; build the current source we have in the upstream repo",
                            defaultValue: false
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
        try {
            stage("build") {
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
                if (params.RELEASE_PAYLOADS) {
                    for (nightly in commonlib.parseList(params.RELEASE_PAYLOADS)) {
                        cmd << "--payload" << nightly.trim()
                    }
                }
                if (params.NO_REBASE) {
                    cmd << "--no-rebase"
                }
                withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'), string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN')]) {
                    echo "Will run ${cmd}"
                    if (params.IGNORE_LOCKS) {
                        commonlib.shell(script: cmd.join(' '))
                    } else {
                        lock("build-microshift-lock-${params.BUILD_VERSION}") { commonlib.shell(script: cmd.join(' ')) }
                    }
                }
            }
            stage("Update pocket") {
                if (!params.UPDATE_POCKET || params.DRY_RUN) {
                    echo "No need to update the pocket."
                    return
                }
                // TODO: For assembly with a basis event, we need to pin the microshift build to the assembly before updating the pocket.
                // Auto-merge the PR before running update-microshift-pocket?
                build(
                    job: "build%2Fupdate-microshift-pocket",
                    propagate: true,
                    parameters: [
                        string(name: 'BUILD_VERSION', value: params.BUILD_VERSION),
                        string(name: 'ASSEMBLY', value: params.ASSEMBLY),
                        // Hardcode RHEL version 8 until we start building for RHEL 9.
                        string(name: 'RHEL_TARGET', value: '8'),
                    ]
                )
            }
        } finally {
            stage("save artifacts") {
                commonlib.safeArchiveArtifacts([
                    "artcd_working/email/**",
                    "artcd_working/**/*.json",
                    "artcd_working/**/*.log",
                ])
            }
        }
    }
}
