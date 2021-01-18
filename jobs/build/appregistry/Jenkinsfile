// This will likely only make sense once you understand https://mojo.redhat.com/docs/DOC-1203429

node('covscan') {
    checkout scm
    def appregistry = load("appregistry.groovy")
    def commonlib = appregistry.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("appregistry", """
        <h2>Manage OLM operator manifests in appregistry format</h2>
        <b>Timing</b>:
        * dev: ocp4 and custom jobs run this automatically
        * stage: release-artists run to hand off new images for QE to verify in a release
        * prod: release-artists run for a verified release when we are CERTAIN it will ship next

        Stage and prod builds for different versions MUST be pushed in the same order they are built.
        <b>The first PROD build should not be performed until AT LEAST Friday before a release.</b>

        For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/appregistry/README.md" target="_blank">README</a>
    """)

    // Please update README.md if modifying parameter names or semantics
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '60',
                    daysToKeepStr: '60')
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: 'BUILD_VERSION',
                        description: 'OSE Version',
                        choices: ['4.5', '4.4', '4.3', '4.2', '4.1'].join('\n'),
                    ),
                    string(
                        name: 'IMAGES',
                        description: 'List of image distgits to limit selection (default all)',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'STREAM',
                        description: 'OMPS appregistry',
                        choices: ['dev', 'stage', 'prod'],
                    ),
                    string(
                        name: 'OLM_OPERATOR_ADVISORIES',
                        description: 'One or more advisories where OLM operators are attached\n* Required for "stage" and "prod" STREAMs',
                        defaultValue: '',
                        trim: true,
                    ),
                    string(
                        name: 'METADATA_ADVISORY',
                        description: 'Advisory to attach corresponding metadata builds\n* Required for "stage" and "prod" STREAMs',
                        defaultValue: '',
                        trim: true,
                    ),
                    booleanParam(
                        name: 'FORCE_METADATA_BUILD',
                        defaultValue: false,
                        description: "Always attempt to build the operator metadata repo, even if the content is unchanged",
                    ),
                    booleanParam(
                        name: 'SKIP_PUSH',
                        defaultValue: false,
                        description: "Do not push operator metadata",
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-appregistry@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )   // Please update README.md if modifying parameter names or semantics

    def workDir = "${env.WORKSPACE}/workDir"
    appregistry.initialize(workDir)

    currentBuild.description = "Collecting appregistry images for ${appregistry.buildVersion} (${params.STREAM} stream)"
    currentBuild.displayName += " - ${appregistry.buildVersion}-${params.STREAM}"
    if (params.STREAM in ['prod', 'stage']) {
        currentBuild.displayName += " (extras: ${params.OLM_OPERATOR_ADVISORIES}, metadata: ${params.METADATA_ADVISORY})"
    }


    def skipPush = params.SKIP_PUSH

    try {
        def operatorBuilds = []
        sshagent(["openshift-bot"]) {
            stage("validate params") {
                if (!appregistry.validate(params)) {
                    error "Parameter validation failed"
                }
            }
            stage("fetch appregistry images") {
                operatorBuilds = appregistry.stageFetchOperatorImages()
                writeYaml file: "${workDir}/appreg.yaml", data: operatorBuilds
                currentBuild.description = "appregistry images collected for ${appregistry.buildVersion}."
            }
            stage("build metadata container") {
                lock("appregistry-build-${params.STREAM}") {
                    appregistry.stageBuildMetadata(operatorBuilds)
                }
            }
            stage("push metadata") {
                if (skipPush) {
                    currentBuild.description += "\nskipping metadata push."
                    return
                }
                if (!operatorBuilds) {
                    currentBuild.description += "\nno operator metadata to push."
                    return
                }

                if (params.STREAM == 'dev') {
                    currentBuild.description += "\npushing operator metadata."
                    withCredentials([usernamePassword(
                        credentialsId: 'quay_appregistry_omps_bot',
                        usernameVariable: 'QUAY_USERNAME',
                        passwordVariable: 'QUAY_PASSWORD',
                    )]) {
                        lock("appregistry-push-dev") {
                            appregistry.stagePushDevMetadata(operatorBuilds)
                        }
                    }
                }
            }
            stage("attach metadata to advisory") {
                if (!params.METADATA_ADVISORY) {
                    currentBuild.description += "\nskipping attach to advisory."
                    return
                }
                lock("appregistry-attach-${appregistry.buildVersion}") {
                    appregistry.stageAttachMetadata(operatorBuilds)
                }
            }
            stage("slack notification to release channel") {
                if (params.STREAM == 'dev') {
                    echo "Skipping Slack notification"
                    return
                }

                metadataNVRs = appregistry.getMetadataNVRs(operatorBuilds.collect { it.nvr }, params.STREAM)

                slacklib.to(params.BUILD_VERSION).say("""
                *:heavy_check_mark: appregistry ${params.STREAM}:*
                The following builds were attached to advisory ${params.METADATA_ADVISORY}:
                ```
                ${metadataNVRs.join('\n')}
                ```

                buildvm job: ${commonlib.buildURL('console')}
                """)
            }
        }
    } catch (err) {
        currentBuild.description = "Job failed: ${err}\n-----------------\n${currentBuild.description}"
        if (skipPush) { return }  // don't spam on failures we don't care about

        if (params.STREAM == 'stage' || params.STREAM == 'prod') {
            slacklib.to(params.BUILD_VERSION).say("""
            *:heavy_exclamation_mark: appregistry ${params.STREAM} failed*
            buildvm job: ${commonlib.buildURL('console')}
            """)
        }

        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Unexpected error during appregistry job",
            body: "Console output: ${commonlib.buildURL('console')}\n${currentBuild.description}",
        )

        throw err
    } finally {
        commonlib.safeArchiveArtifacts([
            "workDir/*",
        ])
    }
}
