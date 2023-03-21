#!/usr/bin/env groovy

node('covscan') {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("build-sync", """
        <h2>Mirror latest 4.y images to nightlies</h2>
        <b>Timing</b>: usually automated. Human might use to revert or hand-advance nightly membership.

        This job gets the latest images from our candidate tags, syncs them to quay.io,
        and updates the imagestreams on api.ci which feed into nightlies on our
        release-controllers.

        build-sync runs a comprehensive set of checks validating the internal consistency
        of the proposed imagestream, and may halt the process accordingly. It can be considered
        the main artbiter.

        For more details see the <a href="https://github.com/openshift-eng/aos-cd-jobs/blob/master/jobs/build/build-sync/README.md" target="_blank">README</a>
    """)

    // Please update README.md if modifying parameter names or semantics
    properties([
        disableResume(),
        buildDiscarder(
          logRotator(
              artifactDaysToKeepStr: '60',
              daysToKeepStr: '60',
          )
        ),
        [
            $class: 'ParametersDefinitionProperty',
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
                    defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                    trim: true,
                ),
                booleanParam(
                    name        : 'EMERGENCY_IGNORE_ISSUES',
                    description : ['Ignore all issues with constructing payload. ',
                                   'In gen-payload, viable will be true whatever is the case, ',
                                   'making internal consistencies in the nightlies possible.<br/>',
                                   '<b/>Do not use without approval.</b>'].join(' '),
                    defaultValue: false,
                ),
                booleanParam(
                    name        : 'RETRIGGER_CURRENT_NIGHTLY',
                    description : ['Forces the release controller to re-run with existing images, ',
                                   'by marking the current ImageStream as new again for Release Controller. ',
                                   'No change will be made to payload images in the release.',
                                   '<br/><b/>Purpose:</b> To run tests again on an already existing nightly. ',
                                   'All other parameters will be ignored.'].join(' '),
                    defaultValue: false,
                ),
                string(
                    name: 'DOOZER_DATA_GITREF',
                    description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                    defaultValue: "",
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
                    name        : 'SKIP_MULTI_ARCH_PAYLOAD',
                    description : 'If group/assembly has multi_arch.enabled, you can bypass --apply-multi-arch and the generation of a heterogeneous release payload by setting this to true',
                    defaultValue: false,
                ),
            ],
        ]
    ])  // Please update README.md if modifying parameter names or semantics

    commonlib.checkMock()

    stage("Initialize") {
        echo("Initializing ${params.BUILD_VERSION} sync: #${currentBuild.number}")
        currentBuild.displayName = "${BUILD_VERSION} - ${ASSEMBLY}"

        // doozer_working must be in WORKSPACE in order to have artifacts archived
        mirrorWorking = "${env.WORKSPACE}/MIRROR_working"
        buildlib.cleanWorkdir(mirrorWorking)

        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }

        def arches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()
        if ( params.EXCLUDE_ARCHES ) {
            excludeArches = commonlib.parseList(params.EXCLUDE_ARCHES)
            currentBuild.displayName += " [EXCLUDE ${excludeArches.join(', ')}]"
            if ( !arches.containsAll(excludeArches) )
                error("Trying to exclude arch ${excludeArches} not present in known arches ${arches}")
            arches.removeAll(excludeArches)
        }
        currentBuild.description = "Arches: ${arches.join(', ')}"

        if ( params.DEBUG ) {
            logLevel = " --loglevel=5 "
        }

        imageList = commonlib.cleanCommaList(params.IMAGES)
        if ( imageList ) {
            echo("Only syncing specified images: ${imageList}")
            currentBuild.description += "<br>Images: ${imageList}"
        }

        failCountFile = "${BUILD_VERSION}-assembly.${ASSEMBLY}.count"
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        echo "${buildlib.DOOZER_BIN}"
        sh "oc version -o yaml"
    }

    stage ("build sync") {
        sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
        ]
        if (params.DRY_RUN) {
            cmd << "--dry-run"
        }
        cmd += [
            "build-sync",
            "--version=${params.BUILD_VERSION}",
            "--assembly=${params.ASSEMBLY}"
        ]
        if (params.PUBLISH) {
            cmd << "--publish"
        }
        cmd << "--data-path=${params.DOOZER_DATA_PATH}"
        if (params.EMERGENCY_IGNORE_ISSUES) {
            cmd << "--emergency-ignore-issues"
        }
        if (params.RETRIGGER_CURRENT_NIGHTLY) {
            cmd << "--retrigger-current-nightly"
        }
        if (params.DOOZER_DATA_GITREF) {
            cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
        }
        if (params.DEBUG) {
            cmd << "--debug"
        }
        if (params.IMAGES) {
            cmd << "--images=${params.IMAGES}"
        }
        if (params.EXCLUDE_ARCHES) {
            cmd << "--exclude-arches=${params.EXCLUDE_ARCHES}"
        }
        if (params.SKIP_MULTI_ARCH_PAYLOAD) {
            cmd << "--skip-multiarch-payload"
        }

        // Run pipeline
        echo "Will run ${cmd}"

        try {
            buildlib.withAppCiAsArtPublish() {
                withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')]) {
                    sh(script: cmd.join(' '), returnStdout: true)
                }
            }

            // Successful buildsync, reset fail count
            writeFile file: failCountFile, text: "0"

            if (params.PUBLISH && !params.DRY_RUN) {
                currentBuild.description += " [PUBLISH]"
            }
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
                msg = "Pipeline has failed to assemble release payload for ${BUILD_VERSION} (assembly ${ASSEMBLY}) ${failCount} times."
                // TODO: https://issues.redhat.com/browse/ART-5657
                artNotifyFrequency = 2
                forumReleaseNotifyFrequency = 5
                if (failCount > 10 && failCount <= 50) {
                    artNotifyFrequency = 5
                    forumReleaseNotifyFrequency = 10
                }
                if (failCount > 50 && failCount <= 200) {
                    artNotifyFrequency = 10
                    forumReleaseNotifyFrequency = 50
                }
                if (failCount > 200) {
                    artNotifyFrequency = 100
                    forumReleaseNotifyFrequency = 100
                }
                if (failCount % artNotifyFrequency == 0) {  // spam ourselves a little more often than forum-release
                    slacklib.to(params.BUILD_VERSION).failure(msg)
                }
                if (assembly == "stream" && (failCount % forumReleaseNotifyFrequency == 0)) {
                    if (commonlib.ocpReleaseState[BUILD_VERSION]['release'].isEmpty()) {
                        // For development releases, notify TRT and release artists
                        slacklib.to("#forum-release-oversight").failure("@release-artists ${msg}")
                    } else {
                        // For GA releases, let forum-release know why no new builds
                        slacklib.to("#forum-release").failure(msg)
                    }
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
            artifacts = []
            artifacts.addAll(["app.ci-backup.tgz", "gen-payload-artifacts/*", "MIRROR_working/debug.log"])
            commonlib.safeArchiveArtifacts(artifacts)
            sh "rm -rf ${env.WORKSPACE}/doozer_working"  // do not use cleanWorkspace as this will remove failure count
            sh "rm -rf ${mirrorWorking}"
        }
    } // stage build-sync
}
