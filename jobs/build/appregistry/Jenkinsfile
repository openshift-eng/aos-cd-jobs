// This will likely only make sense once you understand https://mojo.redhat.com/docs/DOC-1203429

node {
    checkout scm
    def appregistry = load("appregistry.groovy")
    def commonlib = appregistry.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'IMAGES',
                        description: '(Optional) List of images to limit selection (default all)',
                        defaultValue: ""
                    ),
                    [
                        name: 'STREAM',
                        description: 'OMPS appregistry',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: ['dev', 'stage', 'prod'],
                        defaultValue: 'dev',
                    ],
                    string(
                        name: 'OLM_OPERATOR_ADVISORIES',
                        description: 'One or more advisories where OLM operators are attached\n* Required for "stage" and "prod" STREAMs',
                        defaultValue: '',
                    ),
                    string(
                        name: 'METADATA_ADVISORY',
                        description: 'Advisory to attach corresponding metadata builds\n* Required for "stage" and "prod" STREAMs',
                        defaultValue: '',
                    ),
                    booleanParam(
                        name: 'FORCE_METADATA_BUILD',
                        defaultValue: false,
                        description: "Always attempt to build the operator metadata repo, even if there is nothing new to be built"
                    ),
                    booleanParam(
                        name: 'SKIP_PUSH',
                        defaultValue: false,
                        description: "Do not push operator metadata"
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-appregistry@redhat.com',
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    def workDir = "${env.WORKSPACE}/workDir"
    appregistry.initialize(workDir)

    currentBuild.description = "Collecting appregistry images for ${appregistry.buildVersion} (${params.STREAM} stream)"
    currentBuild.displayName += " - ${appregistry.buildVersion} (${params.STREAM})"

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
        }
    } catch (err) {
        currentBuild.description = "Job failed: ${err}\n-----------------\n${currentBuild.description}"
        if (skipPush) { return }  // don't spam on failures we don't care about
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
