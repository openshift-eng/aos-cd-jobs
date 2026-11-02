// This worker triggers one or more downstream rhcos_sync builds and BLOCKS until every
// one of them completes (pyartcd gathers the arches concurrently and waits). Those builds
// can run for a long time and emit no activity in THIS job's log while we wait, so an
// activity-based timeout would fire mid-wait. Use a generous FIXED timeout instead.
timeout(time: 8, unit: 'HOURS') {
    node() {
        timestamps {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib
        commonlib.describeJob("rhcos-sync-fast-channel", """
            <h2>Auto-publish RHCOS boot-image bumps for a z-stream y-stream</h2>
            For a single OCP y-stream, this job queries the Cincinnati <b>fast</b>
            channel for the release end users are currently receiving, extracts the
            RHCOS build id referenced by that release, and compares it against the
            <code>rhcos-id.txt</code> currently published on mirror.openshift.com.
            If the id differs, it triggers the existing <b>rhcos_sync</b> job with
            <code>sign_only=False</code> to publish the updated z-stream boot images.
            If it matches (or the fast channel is empty, e.g. pre-GA), it is a no-op.

            <b>Timing</b>: Run per y-stream by the scheduled job of the same name.
            It may also be run manually for a single version to force an evaluation.
        """)

        def artcd_working = "${WORKSPACE}/artcd_working"

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
                        commonlib.ocpVersionParam('VERSION', '4plus'),
                        booleanParam(
                            name: 'FORCE',
                            description: 'Trigger sync even if the mirror already appears current',
                            defaultValue: false,
                        ),
                        string(
                            name: 'MAIL_LIST_FAILURE',
                            description: 'Failure Mailing List',
                            defaultValue: [
                                'aos-art-automation+failed-rhcos-sync-fast-channel@redhat.com',
                            ].join(','),
                            trim: true,
                        ),
                        commonlib.dryrunParam(),
                        commonlib.mockParam(),
                    ]
                ],
                disableResume()
            ]
        )

        commonlib.checkMock()

        stage("Initialize") {
            currentBuild.displayName = "#${currentBuild.number} ${params.VERSION}"

            if (params.DRY_RUN) {
                currentBuild.displayName += " [DRY_RUN]"
            }

            buildlib.cleanWorkdir(artcd_working, true)
        }

        stage("Sync") {
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
                "rhcos-sync-fast-channel",
                "--version=${params.VERSION}",
            ]
            if (params.FORCE) {
                cmd << "--force"
            }

            // Run pipeline.
            // The command needs:
            //   - Jenkins SA credentials: to trigger the rhcos_sync job via the
            //     pyartcd jenkins client when a boot-image bump is detected.
            //   - QUAY_AUTH_FILE + app.ci KUBECONFIG (via withAppCiAsArtPublish):
            //     to `oc` the fast-channel release payload for RHCOS metadata.
            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                        string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                        string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                        file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE')
                    ]) {
                    wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                    }

                    withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        try {
                            echo "Will run ${cmd.join(' ')}"

                            // artcd blocks until all triggered downstream rhcos_sync builds
                            // finish, which can take hours with no log activity here. Use a
                            // generous FIXED timeout so a quiet wait does not kill the worker.
                            timeout(time: 6, unit: 'HOURS') {
                                sh(script: cmd.join(' '), returnStdout: true)
                            }

                        } catch (err) {
                            echo "Error running ${params.VERSION} rhcos-sync-fast-channel:\n${err}"
                            commonlib.email(
                                to: "${params.MAIL_LIST_FAILURE}",
                                from: "aos-art-automation@redhat.com",
                                replyTo: "aos-team-art@redhat.com",
                                subject: "Unexpected error during rhcos-sync-fast-channel!",
                                body: "Encountered an unexpected error while running rhcos-sync-fast-channel for ${params.VERSION}: ${err}"
                            )
                            throw err

                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                            ])
                            buildlib.cleanWorkspace()
                        }
                    } // withEnv
                } // withCredentials
            } // withAppCiAsArtPublish
        } // stage
    }
        }
}
