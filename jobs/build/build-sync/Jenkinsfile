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
                                    artifactDaysToKeepStr: '365',
                                    daysToKeepStr: '365',
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
                                            name        : 'BREW_EVENT_ID',
                                            description : '(Optional) Look for the last images as of the given Brew event instead of latest',
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
        // // An incident where a bug in oc destroyed the content of a critical imagestream ocp:is/release uncovered the fact that this vital data was not being backed up by any process.
        // DPTP will be asked to backup etcd on this cluster, but ART should also begin backing up these imagestreams during normal operations as a first line of defense.
        // In the build-sync job, prior to updating the 4.x-art-latest imagestreams, a copy of all imagestreams in the various release controller namespaces should be performed.
        stage("backup imagestreams") { build.backupAllImageStreams() }
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
