#!/usr/bin/env groovy
import groovy.transform.Field

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def slacklib = commonlib.slacklib
    def quay_url = "quay.io/openshift-release-dev/ocp-release"

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
                    [
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (e.g. 4.1.0-0.nightly-2019-04-22-005054)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'RELEASE_TYPE',
                        description: 'Select [1. Standard Release] unless discussed with team lead ',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                                '1. Standard Release (Named, Signed, Previous, All Channels)',
                                '2. Release Candidate (Named, Signed, Previous, Candidate Channel)',
                                '3. Feature Candidate (No name, Signed - rpms may not be, Previous, Candidate Channel)',
                                '4. Hotfix (No name, Signed, No Previous, All Channels)'
                        ].join('\n'),
                        defaultValue: '1. Standard Release'
                    ],
                    [
                        name: 'NAME',
                        description: 'Release Type [1] (e.g. 4.1.0) or [2] (e.g. 4.1.0-rc.0); Do not specify for [3] or [4].',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DESCRIPTION',
                        description: 'Should be empty unless you know otherwise',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY',
                        description: 'Optional: Image release advisory number. N/A for direct nightly release. If not given, the number will be retrieved from ocp-build-data.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'PREVIOUS',
                        description: 'Use auto to be prompted later in the job with suggested previous. Otherwise, follow item #6 "PREVIOUS" of the following doc for instructions on how to fill this field:\nhttps://mojo.redhat.com/docs/DOC-1201843#jive_content_id_Completing_a_4yz_release',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "auto"
                    ],
                    [
                        name: 'PERMIT_PAYLOAD_OVERWRITE',
                        description: 'DO NOT USE without team lead approval. Allows the pipeline to overwrite an existing payload in quay.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'SKIP_CINCINNATI_PR_CREATION',
                        description: 'DO NOT USE without team lead approval. This is an unusual option.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'SKIP_OTA_SLACK_NOTIFICATION',
                        description: 'Do not notify OTA team in slack for new PRs',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'PERMIT_ALL_ADVISORY_STATES',
                        description: 'DO NOT USE without team lead approval. Allows release job to run when advisory is not in QE state.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        // https://coreos.slack.com/archives/CJARLA942/p1587651980096400?thread_ts=1587623714.067700&cid=CJARLA942
                        name: 'OPEN_NON_X86_PR',
                        description: 'Usually PRs will only be opened when x86_64 releases are created. If set, this will force their creation for any CPU arch.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'SKIP_IMAGE_LIST',
                        description: 'Do not gather an advisory image list for docs. Use this for RCs and other test situations.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'DRY_RUN',
                        description: 'Only do dry run test and exit.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-art-automation+new-release@redhat.com',
                        ].join(',')
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    direct_release_nightly = false
    detect_previous = true
    candidate_pr_only = false
    if (params.RELEASE_TYPE.startsWith('1.')) {
        // Nothing special, just release it
    } else if (params.RELEASE_TYPE.startsWith('2.')) { // Release candidate (after code freeze)
        candidate_pr_only = true
    } else if (params.RELEASE_TYPE.startsWith('3.')) { // Early release candidate (around feature complete)
        direct_release_nightly = true
        candidate_pr_only = true
    } else if (params.RELEASE_TYPE.startsWith('4.')) {   // Just a hotfix for a specific customer
        direct_release_nightly = true
        detect_previous = false
    } else {
        error('Unknown release type: ' + params.RELEASE_TYPE)
    }

    slackChannel = slacklib.to(FROM_RELEASE_TAG)
    slackChannel.task("Public release prep for: ${FROM_RELEASE_TAG}") {
        taskThread ->
        sshagent(['aos-cd-test']) {
            release_info = ""
            if ( direct_release_nightly ) {
                if ( params.NAME.trim() != '' ) {
                    error('Leave name field blank for direct nightly release')
                }
                release_name = params.FROM_RELEASE_TAG.trim()
            } else {
                release_name = params.NAME.trim()
            }
            name = release_name

            from_release_tag = params.FROM_RELEASE_TAG.trim()
            arch = release.getReleaseTagArch(from_release_tag)
            archSuffix = release.getArchSuffix(arch)
            RELEASE_STREAM_NAME = "4-stable${archSuffix}"
            dest_release_tag = release.destReleaseTag(release_name, arch)
            def (major, minor) = commonlib.extractMajorMinorVersionNumbers(release_name)


            description = params.DESCRIPTION
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0
            String errata_url
            Map release_obj
            def CLIENT_TYPE = 'ocp'

            currentBuild.displayName += "- ${name}"
            if (params.DRY_RUN) {
                currentBuild.displayName += " (dry-run)"
                currentBuild.description += "[DRY RUN]"
            }

            PREVIOUS_LIST_STR = params.PREVIOUS
            if ( params.PREVIOUS.trim() == 'auto' ) {
                taskThread.task('Gather PREVIOUS for release') {

                    if (!detect_previous) {
                        // Hotfixes don't get a PREVIOUS by default since we don't
                        // want customers upgrading to it unintentionally.
                        PREVIOUS_LIST_STR = ''
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
                                        description: "This is release ${NAME}. What release is in flight for the previous minor release 4.${prevMinor}?",
                                        name: 'IN_FLIGHT_PREV',
                                ),
                                string(
                                        defaultValue: "${suggest_previous}",
                                        description: (acquire_failure?acquire_failure:"Doozer thinks these are the other releases to include.") + " Edit as necessary (comma delimited).",
                                        name: 'SUGGESTED',
                                ),
                            ]
                        )

                        def splitlist = resp.SUGGESTED.replaceAll("\\s","").split(',').toList()
                        def inflight = resp.IN_FLIGHT_PREV.trim()
                        if ( inflight ) {
                            splitlist << inflight
                        }
                        PREVIOUS_LIST_STR = splitlist.unique().join(',')
                    }
                }
            }

            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("validation") {
                if (direct_release_nightly) {
                    // No advisory dance
                    advisory = -1
                    errata_url = ''
                    return
                }
                def retval = release.stageValidation(quay_url, dest_release_tag, advisory, params.PERMIT_PAYLOAD_OVERWRITE, params.PERMIT_ALL_ADVISORY_STATES)
                advisory = advisory?:retval.advisoryInfo.id
                errata_url = retval.errataUrl
            }
            stage("build payload") { release.stageGenPayload(quay_url, release_name, dest_release_tag, from_release_tag, description, PREVIOUS_LIST_STR, errata_url) }

            stage("tag stable") {
                if (direct_release_nightly) {
                    // If we are releasing a nightly directly, we don't tag it into release and
                    // if never goes into 4-stable.
                    return
                }
                release.stageTagRelease(quay_url, release_name, dest_release_tag, arch)
            }

            stage("request upgrade tests") {
                if (direct_release_nightly) {
                    // If we are releasing a nightly directly, we don't tag it into release and
                    // if never goes into 4-stable.
                    return
                }
                try {  // don't let a slack outage break the job
                    def previousList = PREVIOUS_LIST_STR.trim().tokenize('\t ,')
                    def modeOptions = [ 'aws', 'gcp', 'azure,mirror' ]
                    def testIndex = 0
                    def testLines = []
                    for ( String from_release : previousList) {
                        mode = modeOptions[testIndex % modeOptions.size()]
                        testLines << "test upgrade ${from_release} ${NAME} ${mode}"
                        testIndex++
                    }
                    slackChannel.say("Hi @release-artists . A new release is ready and needs some upgrade tests to be triggered. "
                        + "Please open a chat with @cluster-bot and issue each of these lines individually:\n${testLines.join('\n')}")
                    currentBuild.description += "\n@cluster-bot requests:\n${testLines.join('\n')}\n"
                } catch(ex) {
                    echo "slack notification failed: ${ex}"
                }
            }

            stage("wait for stable") {
                if (direct_release_nightly) {
                    // If we are releasing a nightly directly, we don't tag it into release and
                    // if never goes into 4-stable.
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
                if (direct_release_nightly) {
                    // No advisory work if we are promoting a nightly directly
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

            stage("advisory update") {
                if (direct_release_nightly) {
                    return
                }
                release.stageAdvisoryUpdate()
            }

            stage("cross ref check") {
                if (direct_release_nightly) {
                    return
                }
                release.stageCrossRef()
            }

            stage("send release message") {
                if (direct_release_nightly) {
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
                        key_name: "redhatrelease2",
                        arch: arch,
                        digest: payloadDigest,
                        client_type: "ocp",
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
Release Page: https://openshift-release${archSuffix}.svc.ci.openshift.org/releasestream/4-stable${archSuffix}/release/${release_name}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${dest_release_tag}

${release_info}
        """);
    }
}
