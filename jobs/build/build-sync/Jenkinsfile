#!/usr/bin/env groovy

node {

    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("build-sync", """
        <h2>Mirror latest 4.y images to nightlies</h2>
        <b>Timing</b>: usually automated. Human might use to revert or hand-advance nightly membership.

        This job gets the latest images from our candidate tags, syncs them to quay.io,
        and updates the imagestreams on api.ci which feed into nightlies on our
        release-controllers.

        For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/build-sync/README.md" target="_blank">README</a>
    """)

    // Please update README.md if modifying parameter names or semantics
    properties(
            [
                    disableResume(),
                    buildDiscarder(
                            logRotator(
                                    artifactDaysToKeepStr: '60',
                                    daysToKeepStr: '60',
                            )
                    ),
                    [
                            $class              : 'ParametersDefinitionProperty',
                            parameterDefinitions: [
                                    commonlib.suppressEmailParam(),
                                    commonlib.mockParam(),
                                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                                    commonlib.doozerParam(),
                                    string(
                                        name: 'ASSEMBLY',
                                        description: 'The name of an assembly to sync.',
                                        defaultValue: "stream",
                                        trim: true,
                                    ),
                                    booleanParam(
                                            name        : 'PUBLISH',
                                            description : 'Publish release image(s) directly to registry.ci for testing',
                                            defaultValue: false,
                                    ),
                                    string(
                                        name: 'DOOZER_DATA_PATH',
                                        description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                                        defaultValue: "https://github.com/openshift/ocp-build-data",
                                        trim: true,
                                    ),
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
                                    booleanParam(
                                            name        : 'TRIGGER_NEW_NIGHTLY',
                                            description : 'Forces the release controller to re-run with existing images; no change will be made to payload images in the release. All other parameters will be ignored.',
                                            defaultValue: false,
                                    ),
                                    string(
                                            name        : 'IMAGES',
                                            description : '(Optional) Limited list of images to sync, for testing purposes',
                                            defaultValue: "",
                                            trim: true,
                                    ),
                                    string(
                                            name        : 'EXCLUDE_ARCHES',
                                            description : '(Optional) List of problem arch(es) NOT to sync (aarch64, ppc64le, s390x, x86_64)',
                                            defaultValue: "",
                                            trim: true,
                                    ),
                                    booleanParam(
                                            name        : 'EMERGENCY_IGNORE_ISSUES',
                                            description : 'Ignore all issues with constructing payload. Do not use without approval.',
                                            defaultValue: false,
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
        echo "${buildlib.DOOZER_BIN}"
        sh "oc version -o yaml"
    }

    failCountFile = "${BUILD_VERSION}-assembly.${ASSEMBLY}.count"
    currentBuild.displayName = "${BUILD_VERSION} - ${ASSEMBLY}"

    try {

        if (params.TRIGGER_NEW_NIGHTLY && params.ASSEMBLY == "stream" ) {
            if (params.DRY_RUN) {
                echo "Would have triggered new release cut in release controller."
            } else {
                echo "Triggering release controller to cut new release using previously synced builds..."
                buildlib.oc("--kubeconfig ${buildlib.ciKubeconfig} -n ocp tag registry.access.redhat.com/ubi8 ${params.BUILD_VERSION}-art-latest:trigger-release-controller")
                echo "Sleeping so that release controller has time to react..."
                sleep(10)
                buildlib.oc("--kubeconfig ${buildlib.ciKubeconfig} -n ocp tag ${params.BUILD_VERSION}-art-latest:trigger-release-controller -d")
            }
            return
        }

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

        // Successful buildsync, reset fail count
        writeFile file: failCountFile, text: "0"

    } catch (err) {
        failCount = 1
        if (fileExists(failCountFile)) {
            failCountStr = readFile(failCountFile).trim()
            if (failCountStr.isInteger()) {
                failCount = failCountStr.toInteger() + 1
            }
        }
        writeFile file: failCountFile, text: "${failCount}"

        if (failCount > 1) {
            msg = "@release-artists - pipeline has failed to assemble release payload for ${BUILD_VERSION} (assembly ${ASSEMBLY}) ${failCount} times."
            if (failCount % 2 == 0) {  // spam ourselves a little more often than forum-release
                slacklib.to(params.BUILD_VERSION).failure(msg)
            }
            if (assembly == "stream" && (failCount % 5 == 0)) {  // let forum-release know why no new builds
                slacklib.to("#forum-release").failure(msg)
            }
        }

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
        sh "rm -rf ${env.WORKSPACE}/doozer_working"  // do not use cleanWorkspace as this will remove failure count
        sh "rm -rf ${mirrorWorking}"
    }
}
