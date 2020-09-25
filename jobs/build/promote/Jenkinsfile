#!/usr/bin/env groovy
import groovy.transform.Field

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def slacklib = commonlib.slacklib
    def quay_url = "quay.io/openshift-release-dev/ocp-release"
    commonlib.describeJob("promote", """
        <h2>Publish official OCP 4 release artifacts</h2>
        <b>Timing</b>: <a href="https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-the-release-image" target="_blank">4.y z-stream doc</a>
        Be aware that by default the job stops for user input very early on. It
        sends slack alerts in our release channels when this occurs.

        For the default use case, this job:
        <ul><li>publishes a nightly as an officially named release image
          <li>waits up to three hours for it to be accepted
          <li>enables automation, so builds will run again
          <li>opens pull requests to cinci-graph-data
          <li>copies the clients to the mirror
          <li>signs the clients and release image
          <li>...and handles odds and ends for a release</ul>

        There are minor differences when this job runs for FCs, RCs, or hotfixes.

        Most of what it does can be replicated manually by running other jobs,
        which is useful when it breaks for some reason. See:
        <a href="https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#release-job-failures" target="_blank">Release job failures</a>
    """)


    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (e.g. 4.1.0-0.nightly-2019-04-22-005054)',
                        trim: true,
                    ),
                    choice(
                        name: 'RELEASE_TYPE',
                        description: 'Select [1. Standard Release] unless discussed with team lead',
                        choices: [
                                '1. Standard Release (Named, Signed, Previous, All Channels)',
                                '2. Release Candidate (Named, Signed, Previous, Candidate Channel)',
                                '3. Feature Candidate (Named, Signed - rpms may not be, Previous, Candidate Channel)',
                                '4. Hotfix (No name, Signed, No Previous, All Channels)',
                            ].join('\n'),
                    ),
                    string(
                        name: 'RELEASE_OFFSET',
                        description: 'Integer. Do not specify for hotfix. If offset is X for 4.5 nightly => Release name is 4.5.X for standard, 4.5.0-rc.X for Release Candidate, 4.5.0-fc.X for Feature Candidate ',
                        trim: true,
                    ),
                    string(
                        name: 'DESCRIPTION',
                        description: 'Should be empty unless you know otherwise',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ADVISORY',
                        description: [
                              'Optional: Image release advisory number.',
                              'N/A for direct nightly release.',
                              'If not given, the number will be retrieved from ocp-build-data.',
                              'If "-1", this is skipped (for testing purposes).',
                            ].join(' '),
                        trim: true,
                    ),
                    string(
                        name: 'PREVIOUS',
                        description: 'Use auto to be prompted later in the job with suggested previous. Otherwise, follow item #6 "PREVIOUS" of the following doc for instructions on how to fill this field:\nhttps://mojo.redhat.com/docs/DOC-1201843#jive_content_id_Completing_a_4yz_release',
                        defaultValue: "auto",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'PERMIT_PAYLOAD_OVERWRITE',
                        description: 'DO NOT USE without team lead approval. Allows the pipeline to overwrite an existing payload in quay.',
                        defaultValue: false,
                    ),
                    choice(
                        name: 'ENABLE_AUTOMATION',
                        description: [
                                'Unfreeze automation to enable building and sweeping into the new advisories',
                                '<b>Default</b>: Enable for Standard and RC releases, if arch is x86_64',
                            ].join('<br/>'),
                        choices: [
                            'Default',
                            'Yes',
                            'No',
                        ].join('\n'),
                    ),
                    booleanParam(
                        name: 'SKIP_CINCINNATI_PR_CREATION',
                        description: 'DO NOT USE without team lead approval. This is an unusual option.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_OTA_SLACK_NOTIFICATION',
                        description: 'Do not notify OTA team in slack for new PRs',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'PERMIT_ALL_ADVISORY_STATES',
                        description: 'DO NOT USE without team lead approval. Allows release job to run when advisory is not in QE state.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        // https://coreos.slack.com/archives/CJARLA942/p1587651980096400?thread_ts=1587623714.067700&cid=CJARLA942
                        name: 'OPEN_NON_X86_PR',
                        description: 'Usually PRs will only be opened when x86_64 releases are created. If set, this will force their creation for any CPU arch.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_IMAGE_LIST',
                        description: 'Do not gather an advisory image list for docs. Use this for RCs and other test situations.',
                        defaultValue: false,
                    ),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-art-automation+new-release@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.dryrunParam('Take no actions. Note: still notifies and runs signing job (which fails)'),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    def CLIENT_TYPE = 'ocp'
    ga_release = false
    direct_release_nightly = false
    detect_previous = true
    candidate_pr_only = false
    is_4stable_release = true

    release_offset = params.RELEASE_OFFSET?params.RELEASE_OFFSET.toInteger():0
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.FROM_RELEASE_TAG)

    if (params.RELEASE_TYPE.startsWith('1.')) { // Standard X.Y.Z release
        release_name = "${major}.${minor}.${release_offset}"
        ga_release = true
    } else if (params.RELEASE_TYPE.startsWith('2.')) { // Release candidate (after code freeze)
        candidate_pr_only = true
        release_name = "${major}.${minor}.0-rc.${release_offset}"
    } else if (params.RELEASE_TYPE.startsWith('3.')) { // Feature candidate (around feature complete)
        direct_release_nightly = true
        release_name = "${major}.${minor}.0-fc.${release_offset}"
        candidate_pr_only = true
        CLIENT_TYPE = 'ocp-dev-preview'
    } else if (params.RELEASE_TYPE.startsWith('4.')) {   // Hotfix for a specific customer
        direct_release_nightly = true
        detect_previous = false
        is_4stable_release = false
        // ignore offset. Release is named same as nightly but with 'hotfix' instead of 'nightly'.
        release_name = params.FROM_RELEASE_TAG.trim().replaceAll('nightly', 'hotfix')
        CLIENT_TYPE = 'ocp-dev-preview'  // Trigger beta2 key
    } else {
        error('Unknown release type: ' + params.RELEASE_TYPE)
    }

    slackChannel = slacklib.to(FROM_RELEASE_TAG)
    slackChannel.task("Public release prep for: ${FROM_RELEASE_TAG}${ params.DRY_RUN ? ' (DRY RUN)' : ''}") {
        taskThread ->
        sshagent(['aos-cd-test']) {
            release_info = ""
            name = release_name

            from_release_tag = params.FROM_RELEASE_TAG.trim()
            (arch, priv) = release.getReleaseTagArchPriv(from_release_tag)
            RELEASE_STREAM_NAME = "4-stable${release.getArchPrivSuffix(arch, false)}"
            dest_release_tag = release.destReleaseTag(release_name, arch)

            description = params.DESCRIPTION
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0
            String errata_url
            Map release_obj

            currentBuild.displayName = "${name} (${arch})"
            currentBuild.description = "${from_release_tag} -> ${release_name}"
            if (params.DRY_RUN) {
                currentBuild.displayName += " (dry-run)"
                currentBuild.description += "[DRY RUN]"
            }

            if (priv) {
                currentBuild.displayName += " (EMBARGO)"
                currentBuild.description += " [EMBARGO]"
                taskThread.task('Prompt the artist to confirm that embargo dates have lifted') {
                    commonlib.inputRequired(taskThread) {
                        def resp = input(
                            message: "The release that you are about to promote has embargoes. You should only promote the release if the embargoes have lifted.",
                            parameters: [
                                booleanParam(
                                    defaultValue: false,
                                    description: "Check this checkbox only if the embargoes have lifted. Ask Product Security (prodsec-openshift@redhat.com) if you are not sure.",
                                    name: 'EMBARGO_LIFTED',
                                ),
                            ]
                        )
                        if (!resp) {  // Gotcha: If just one parameter is listed, its value will become the value of the input step instead of a map.
                            currentBuild.result = 'ABORTED'
                            error('Aborting because the embargo has not been lifted.')
                        }
                    }
                }
            }

            previousList = commonlib.parseList(params.PREVIOUS)
            if ( params.PREVIOUS.trim() == 'auto' ) {
                taskThread.task('Gather PREVIOUS for release') {

                    if (!detect_previous) {
                        // Hotfixes don't get a PREVIOUS by default since we don't
                        // want customers upgrading to it unintentionally.
                        previousList = []
                        return
                    }

                    def acquire_failure = ''
                    def suggest_previous = ''
                    try {
                        suggest_previous = buildlib.doozer("release:calc-previous -a ${arch} --version ${release_name}", [capture: true])
                        echo "Doozer suggested: ${suggest_previous}"
                    } catch ( cincy_down ) {
                        acquire_failure = '****Doozer was not able to acquire data from Cincinnati. Inputs will need to be determined manually****. '
                        echo acquire_failure
                    }

                    prevMinor = minor - 1
                    commonlib.inputRequired(taskThread) {
                        def resp = input(
                            message: "${acquire_failure}What PREVIOUS releases should be included in ${release_name} (arch: ${arch})?",
                            parameters: [
                                string(
                                    defaultValue: "4.${prevMinor}.?",
                                    description: "This is release ${release_name}. What release is in flight for the previous minor release 4.${prevMinor}?",
                                    name: 'IN_FLIGHT_PREV',
                                ),
                                string(
                                    defaultValue: "${suggest_previous}",
                                    description: (acquire_failure?acquire_failure:"Doozer thinks these are the other releases to include.") + " Edit as necessary (comma delimited).",
                                    name: 'SUGGESTED',
                                ),
                            ]
                        )

                        previousList = commonlib.parseList(resp.SUGGESTED) + commonlib.parseList(resp.IN_FLIGHT_PREV)
                    }
                }
            }
            previousList = previousList.toList().unique()
            echo "previousList is ${previousList}"

            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("validation") {
                if (direct_release_nightly) {
                    advisory = -1
                }
                if (advisory == -1) {
                    // No advisory dance
                    errata_url = ''
                    return
                }
                def retval = release.stageValidation(quay_url, dest_release_tag, advisory, params.PERMIT_PAYLOAD_OVERWRITE, params.PERMIT_ALL_ADVISORY_STATES)
                advisory = advisory?:retval.advisoryInfo.id
                errata_url = retval.errataUrl
            }
            stage("build payload") { release.stageGenPayload(quay_url, release_name, dest_release_tag, from_release_tag, description, previousList.join(','), errata_url) }

            stage("tag stable") {
                if (!is_4stable_release) {
                    // Something like a hotfix should not go into 4-stable in the release controller
                    return
                }
                release.stageTagRelease(quay_url, release_name, dest_release_tag, arch)
            }

            stage("request upgrade tests") {
                if (direct_release_nightly || !is_4stable_release) {
                    // For a hotfix, there is speed is our goal. Assume testing has already been done.
                    // For an FC, we are so early in the release cycle that non-default upgrade tests are
                    // only noise.
                    return
                }
                try {  // don't let a slack outage break the job at this point
                    def modeOptions = [ 'aws', 'gcp', 'azure,mirror' ]
                    def testIndex = 0
                    def testLines = []
                    for ( String from_release : previousList) {
                        mode = modeOptions[testIndex % modeOptions.size()]
                        testLines << "test upgrade ${from_release} ${release_name} ${mode}"
                        testIndex++
                    }
                    currentBuild.description += "\n@cluster-bot requests:\n${testLines.join('\n')}\n"
                    if (params.DRY_RUN) {
                        echo "DRY_RUN: Not slacking release-artists to run these:\n${testLines.join('\n')}"
                        return
                    }
                    slackChannel.say("Hi @release-artists . A new release is ready and needs some upgrade tests to be triggered. "
                        + "Please open a chat with @cluster-bot and issue each of these lines individually:\n${testLines.join('\n')}")
                } catch(ex) {
                    echo "slack notification failed: ${ex}"
                }
            }

            stage("enable automation") {
                try {
                    if (params.ENABLE_AUTOMATION == 'No') {
                        echo 'Not enabling automation because ENABLE_AUTOMATION is set to No'
                        return
                    }
                    if (params.ENABLE_AUTOMATION == 'Default' && arch != 'x86_64') {
                        echo "Not enabling automation because that is not Default behavior for arch ${arch}"
                        return
                    }
                    if (params.ENABLE_AUTOMATION == 'Default' && params.RELEASE_TYPE.startsWith('3.')) {
                        echo "Not enabling automation because that is not Default behavior for Feature Candidates"
                        return
                    }
                    if (params.ENABLE_AUTOMATION == 'Default' && params.RELEASE_TYPE.startsWith('4.')) {
                        echo "Not enabling automation because that is not Default behavior for Hotfixes"
                        return
                    }

                    def branch = "openshift-${major}.${minor}"
                    def edit = [
                        "rm -rf ocp-build-data",
                        "git clone --single-branch --branch ${branch} git@github.com:openshift/ocp-build-data.git",
                        "cd ocp-build-data",
                        "sed -e 's/freeze_automation:.*/freeze_automation: no/' -i group.yml",
                        "git diff",
                    ]

                    if (params.DRY_RUN) {
                        edit << "echo DRY_RUN: neither committing, nor pushing"
                    } else {
                        edit << [
                            "if ! git diff --exit-code --quiet; then",
                            "  git add .",
                            "  git commit -m 'Enable automation'",
                            "  git push origin ${branch}",
                            "fi",
                        ]
                    }

                    def cmd = edit.flatten().join('\n')
                    echo "shell cmd:\n${cmd}"

                    sshagent(["openshift-bot"]) {
                        commonlib.shell(
                            returnStdout: true,
                            script: cmd
                        )
                    }
                } catch(err) {
                    currentBuild.result = "UNSTABLE"
                    currentBuild.description += "Enable automation failed\n"
                    echo "${err}"
                }
            }

            stage("wait for stable") {
                if (!is_4stable_release) {
                    // If it is not in 4-stable, there is nothing to wait for.
                    return
                }
                commonlib.retryAbort("Waiting for stable ${release_name}", taskThread,
                                        "Release ${release_name} is not currently Accepted by release controller. Issue cluster-bot requests for each upgrade test. "
                                         + "RETRY when the release is finally Accepted.")  {
                    release_obj = release.stageWaitForStable(RELEASE_STREAM_NAME, release_name)
                 }
            }

            stage("get release info") {
                release_info = release.stageGetReleaseInfo(quay_url, dest_release_tag)
            }

            stage("advisory image list") {
                if (!ga_release) {
                    echo "No need to send docs an image list for non-GA releases."
                    return
                }
                if (advisory == -1) {
                    echo "Skipping image list for dummy advisory."
                    return
                }
                if (params.SKIP_IMAGE_LIST) {
                    currentBuild.description += "[No image list]"
                    return
                }
                try {
                    filename = "${dest_release_tag}-image-list.txt"
                    retry (3) {
                        commonlib.shell(script: "elliott advisory-images -a ${advisory} > ${filename}")
                    }
                    archiveArtifacts(artifacts: filename, fingerprint: true)
                    if (!params.DRY_RUN) {
                        commonlib.email(
                            to: "openshift-ccs@redhat.com",
                            cc: "aos-art-automation+image-list@redhat.com",
                            replyTo: "aos-team-art@redhat.com",
                            subject: "OCP ${release_name} (${arch}) Image List",
                            body: readFile(filename)
                        )
                    }
                } catch (ex) {
                    currentBuild.description += "Image list failed. Marked UNSTABLE and continuing."
                    currentBuild.result = "UNSTABLE"
                }
            }

            buildlib.registry_quay_dev_login()  // chances are, earlier auth has expired

            stage("mirror tools") {
                retry(3) {
                    release.stagePublishClient(quay_url, dest_release_tag, release_name, arch, CLIENT_TYPE)
                }
            }

            stage("send release message") {
                if (!is_4stable_release) {
                    echo "Not a stable release, not sending message over bus"
                    return
                }
                if (params.DRY_DRUN) {
                    echo "DRY_RUN: Not sending release message"
                    return
                }
                release.sendReleaseCompleteMessage(release_obj, advisory, errata_url, arch)
            }

            stage("sign artifacts") {
                commonlib.retrySkipAbort("Signing artifacts", taskThread, "Error running signing job") {
                    release.signArtifacts(
                        name: name,
                        signature_name: "signature-1",
                        dry_run: params.DRY_RUN,
                        env: "prod",
                        key_name: CLIENT_TYPE=='ocp'?"redhatrelease2":"beta2",
                        arch: arch,
                        digest: payloadDigest,
                        client_type: CLIENT_TYPE,
                    )
                }
            }

            stage("channel prs") {
                if ( params.DRY_RUN ) {
                    echo "Skipping PR creation for DRY_RUN"
                    return
                }
                if ( params.SKIP_CINCINNATI_PR_CREATION ) {
                    echo "SKIP_CINCINNATI_PR_CREATION set; skipping PR creation"
                    return
                }
                if (arch == 'x86_64' || params.OPEN_NON_X86_PR ) {
                    commonlib.retrySkipAbort('Open Cincinnati PRs', taskThread) {
                        build(
                                job: 'build%2Fcincinnati-prs',  propagate: true,
                                parameters: [
                                    buildlib.param('String', 'RELEASE_NAME', release_name),
                                    buildlib.param('String', 'ADVISORY_NUM', "${advisory}"),
                                    booleanParam(name: 'CANDIDATE_CHANNEL_ONLY', value: candidate_pr_only),
                                    buildlib.param('String', 'GITHUB_ORG', 'openshift'),
                                    booleanParam(name: 'SKIP_OTA_SLACK_NOTIFICATION', value: params.SKIP_OTA_SLACK_NOTIFICATION)
                                ]
                        )
                    }
                } else {
                    echo "Skipping PR creation for non-x86 CPU arch"
                }
            }
        }

        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}

        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${release_name} (${arch})",
            body: """
Jenkins Job: ${env.BUILD_URL}
Release Page: https://openshift-release${release.getArchPrivSuffix(arch, false)}.svc.ci.openshift.org/releasestream/4-stable${release.getArchPrivSuffix(arch, false)}/release/${release_name}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${dest_release_tag}

${release_info}
        """);
    }
}
