// activity == true, means that the timeout will only occur if there
// is no log activity for the specified period.
timeout(activity: true, time: 60, unit: 'MINUTES') {
    node() {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib
        commonlib.describeJob("ocp4_scan", """
            <h2>Kick off incremental builds where needed</h2>
            This job scans OCP4 versions for any changes in sources, buildroots,
            etc. and schedules an incremental build if there are any.

            <b>Timing</b>: Run by the scheduled job of the same name, as often as possible
            (which is no more than hourly or so - depending on what has changed).

            <h1>DO NOT RUN THIS MANUALLY *</h1>
            * Humans MAY run this, but be aware that this will cause builds to run
            without respecting freeze_automation. If you just need to test something,
            limit it to a release that's not frozen.
        """)

        def artcd_working = "${WORKSPACE}/artcd_working"
        def doozer_working = "${artcd_working}/doozer_working"

        // Expose properties for a parameterized build
        properties(
            [
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: '20',
                        daysToKeepStr: '20'
                    )
                ),
                [
                    $class: 'ParametersDefinitionProperty',
                    parameterDefinitions: [
                        commonlib.artToolsParam(),
                        commonlib.ocpVersionParam('VERSION', '4'),
                        commonlib.suppressEmailParam(),
                        string(
                            name: 'MAIL_LIST_SUCCESS',
                            description: 'Success Mailing List',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'MAIL_LIST_FAILURE',
                            description: 'Failure Mailing List',
                            defaultValue: [
                                'aos-art-automation+failed-ocp4-scan@redhat.com',
                            ].join(','),
                            trim: true,
                        ),
                        booleanParam(
                            name: 'DRY_RUN',
                            description: 'Run scan without triggering subsequent jobs',
                            defaultValue: false,
                        ),
                        commonlib.mockParam(),
                    ]
                ],
                disableResume()
            ]
        )

        commonlib.checkMock()

        retry(3) {
            buildlib.registry_quay_dev_login()
        }

        stage("Initialize") {
            currentBuild.displayName = "#${currentBuild.number} ${params.VERSION}"

            if (params.DRY_RUN) {
                currentBuild.displayName += "[DRY_RUN]"
            }

            buildlib.cleanWorkdir(artcd_working, true)
        }

        stage("Scan") {
            sshagent(["openshift-bot"]) {
                buildlib.init_artcd_working_dir()
                cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=${artcd_working}",
                    "--config=./config/artcd.toml",
                ]
                if (params.DRY_RUN) {
                    cmd << "--dry-run"
                }
                cmd += [
                    "ocp4-scan",
                    "--version=${params.VERSION}"
                ]

                // Run pipeline
                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                            string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                            string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                            string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')
                        ]) {
                        // There is a vanishingly small race condition here, but it is not dangerous;
                        // it can only lead to undesired delays (i.e. waiting to scan while a build is ongoing).
                        wrap([$class: 'BuildUser']) {
                            builderEmail = env.BUILD_USER_EMAIL
                        }

                        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                            try {
                                echo "Will run ${cmd}"

                                timeout(activity: true, time: 60, unit: 'MINUTES') {
                                    sh(script: cmd.join(' '), returnStdout: true)
                                }

                                // success email only if requested for this build
                                if (params.MAIL_LIST_SUCCESS.trim()) {
                                    commonlib.email(
                                        to: "${params.MAIL_LIST_SUCCESS}",
                                        from: "aos-art-automation@redhat.com",
                                        replyTo: "aos-team-art@redhat.com",
                                        subject: "Success scanning OCP version: ${params.VERSION}",
                                        body: "Success scanning OCP:\n${env.BUILD_URL}"
                                    )
                                }

                            } catch (err) {
                                echo "Error running ${params.VERSION} scan:\n${err}"
                                commonlib.email(
                                    to: "${params.MAIL_LIST_FAILURE}",
                                    from: "aos-art-automation@redhat.com",
                                    replyTo: "aos-team-art@redhat.com",
                                    subject: "Unexpected error during OCP scan!",
                                    body: "Encountered an unexpected error while running OCP scan: ${err}"
                                )
                                throw err

                            } finally {
                                // If scan was skipped, there won't be any logs to archive
                                if (fileExists(doozer_working)) {
                                    sh "mv ${doozer_working}/debug.log ${doozer_working}/debug-${params.VERSION}.log"
                                    sh "bzip2 ${doozer_working}/debug-${params.VERSION}.log"
                                    commonlib.safeArchiveArtifacts(["artcd_working/doozer_working/*.bz2"])
                                }
                                buildlib.cleanWorkspace()
                            }
                        } // withEnv
                    } // withCredentials
                } // withAppCiAsArtPublish
            } // sshagent
        } // stage
    }
}
