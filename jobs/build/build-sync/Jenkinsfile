#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib

    properties(
            [
                    disableResume(),
                    buildDiscarder(
                            logRotator(
                                    artifactDaysToKeepStr: '',
                                    artifactNumToKeepStr: '',
                                    daysToKeepStr: '',
                                    numToKeepStr: ''
                            )
                    ),
                    [
                            $class              : 'ParametersDefinitionProperty',
                            parameterDefinitions: [
                                    commonlib.suppressEmailParam(),
                                    commonlib.mockParam(),
                                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                                    [
                                            name        : 'DEBUG',
                                            description : 'Run "oc" commands with greater logging',
                                            $class      : 'BooleanParameterDefinition',
                                            defaultValue: false,
                                    ],
                                    [
                                            name        : 'NOOP',
                                            description : 'Run "oc" commands with the dry-run option set to true',
                                            $class      : 'BooleanParameterDefinition',
                                            defaultValue: false,
                                    ],
                                    [
                                            name        : 'IMAGES',
                                            description : '(Optional) Comma separated list of images to sync, for testing purposes',
                                            $class      : 'hudson.model.StringParameterDefinition',
                                            defaultValue: "",
                                    ],
                                    [
                                            name        : 'ORGANIZATION',
                                            description : '(Optional) Quay.io organization to mirror to',
                                            $class      : 'hudson.model.StringParameterDefinition',
                                            defaultValue: "openshift-release-dev",
                                    ],
                                    [
                                            name        : 'REPOSITORY',
                                            description : '(Optional) Quay.io repository to mirror to',
                                            $class      : 'hudson.model.StringParameterDefinition',
                                            defaultValue: "ocp-v4.0-art-dev",
                                    ],
                            ],
                    ]
            ]
    )

    commonlib.checkMock()
    echo("Initializing ${params.BUILD_VERSION} sync: #${currentBuild.number}")
    build.initialize()

    stage("Version dumps") {
        buildlib.doozer "--version"
        sh "which doozer"
        sh "oc version -o yaml"
    }

    try {
        // This stage is safe to run concurrently. Each build runs
        // these steps in its own directory.
        stage("Generate inputs") { build.buildSyncGenInputs() }
        // Allow this job to run concurrently for different
        // versions. That is to say, do not allow builds for the same
        // version to run the business logic concurrently.
        lock("mirroring-lock-OCP-${params.BUILD_VERSION}") {
            stage("oc image mirror") { build.buildSyncMirrorImages() }
        }
        lock("oc-applying-lock-OCP-${params.BUILD_VERSION}") {
            stage("oc apply") { build.buildSyncApplyImageStreams() }
        }
    } catch (err) {
        currentBuild.displayName += " [FAILURE]"
        commonlib.email(
                to: "aos-art-automation+failed-build-sync@redhat.com",
                from: "aos-art-automation@redhat.com",
                replyTo: "aos-team-art@redhat.com",
                subject: "Error during OCP ${params.BUILD_VERSION} build sync",
                body: """
There was an issue running build-sync for OCP ${params.BUILD_VERSION}:

    ${err}
""")
        throw (err)
    } finally {
        commonlib.safeArchiveArtifacts(build.artifacts)
    }
}
