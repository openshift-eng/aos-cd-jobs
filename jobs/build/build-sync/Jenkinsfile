#!/usr/bin/env groovy

node {

    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib
    commonlib.describeJob("build-sync", """
        -------------------------------------
        Mirror latest 4.y images to nightlies
        -------------------------------------
        Timing: usually automated. Human might use to revert or hand-advance nightly membership.

        This job gets the latest images from our candidate tags, syncs them to quay.io,
        and updates the imagestreams on api.ci which feed into nightlies on our
        release-controllers.

        For more details see the README:
        https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/build-sync/README.md
    """)

    // Please update README.md if modifying parameter names or semantics
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
                                    booleanParam(
                                            name        : 'DEBUG',
                                            description : 'Run "oc" commands with greater logging',
                                            defaultValue: false,
                                    ),
                                    booleanParam(
                                            name        : 'DRY_RUN',
                                            description : 'Run "oc" commands with the dry-run option set to true',
                                            defaultValue: false,
                                    ),
                                    string(
                                            name        : 'IMAGES',
                                            description : '(Optional) Limited list of images to sync, for testing purposes',
                                            defaultValue: "",
                                    ),
                                    string(
                                            name        : 'BREW_EVENT_ID',
                                            description : '(Optional) Look for the latest images as of the given Brew event instead of current',
                                            defaultValue: "",
                                    ),
                                    string(
                                            name        : 'ORGANIZATION',
                                            description : 'Quay.io organization to mirror to (do not change)',
                                            defaultValue: "openshift-release-dev",
                                    ),
                                    string(
                                            name        : 'REPOSITORY',
                                            description : 'Quay.io repository to mirror to (do not change)',
                                            defaultValue: "ocp-v4.0-art-dev",
                                    ),
                            ],
                    ]
            ]
    )  // Please update README.md if modifying parameter names or semantics

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
