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

        For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/promote/README.md" target="_blank">README</a>
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
                    commonlib.ocpVersionParam('VERSION', '4'),  // not used by "stream" assembly
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to promote.',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (e.g. 4.1.0-0.nightly-2019-04-22-005054). Do not specify for a non-stream assembly.',
                        trim: true,
                    ),
                    choice(
                        name: 'RELEASE_TYPE',
                        description: 'Select [1. Standard Release] unless discussed with team lead. Not used by non-stream assembly.',
                        choices: [
                                '1. Standard Release (Named, Signed, Previous, All Channels)',
                                '2. Release Candidate (Named, Signed, Previous, Candidate Channel)',
                                '3. Feature Candidate (Named, Signed - rpms may not be, Previous, Candidate Channel)',
                                '4. Hotfix (No name, Signed, No Previous, All Channels)',
                            ].join('\n'),
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'The architecture for the release. Use "auto" for promoting nightlies. ARCH must be specified when promoting an assembly or re-promoting an RC."',
                        choices: (['auto'] + commonlib.brewArches).join('\n'),
                    ),
                    string(
                        name: 'RELEASE_OFFSET',
                        description: 'Integer. Do not specify for standard or candidate assembly. If offset is X for 4.5 nightly => Release name is 4.5.X for standard, 4.5.0-rc.X for Release Candidate, 4.5.0-fc.X for Feature Candidate, 4.5.X-assembly.ASSEMBLY_NAME for custom release',
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
                    string(
                        name: 'IN_FLIGHT_PREV',
                        description: 'This is the in flight release version of previous minor version of OCP. Leave blank to be prompted later in the job. "skip" to indicate that there is no such release in flight. Used to fill upgrade suggestions.',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'PERMIT_PAYLOAD_OVERWRITE',
                        description: 'DO NOT USE without team lead approval. Allows the pipeline to overwrite an existing payload in quay.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_VERIFY_BUGS',
                        description: 'For standard release, skip verifying bugs in advisories.<br/>Use to save time on large releases if bugs have already been verified.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_PAYLOAD_CREATION',
                        description: "Don't actually create the payload. This is used to rerun the job to sync tools and sign artifacts without overwriting the payload.",
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
                    choice(
                        name: 'RESUME_FROM',
                        description: 'Select stage to resume from. Useful to execute remaining steps in the case of a failed promote job.',
                        choices: [
                                '0. The beginning',
                                '1. Mirror binaries',
                                '2. Signing',
                                '3. Cincinnati PRs',
                            ].join('\n'),
                    ),
                    booleanParam(
                        name: 'SKIP_ATTACH_CVE_FLAWS',
                        description: 'Skip elliott attach-cve-flaws step',
                        defaultValue: false,
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
                        description: 'DO NOT USE without team lead approval. Allows "Standard" promotion when advisory is not in QE state.',
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
                        description: '(Standard Release) Do not gather an advisory image list for docs.',
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
    is_prerelease = false
    is_4stable_release = true
    next_is_prerelease = false
    def release_config = null
    def (major, minor) = [0, 0]

    // copy job params into normal vars, since params is an immutable map
    def skip = [
        PAYLOAD_CREATION: params.SKIP_PAYLOAD_CREATION,
        VERIFY_BUGS: params.SKIP_VERIFY_BUGS,
        IMAGE_LIST: params.SKIP_IMAGE_LIST,
        TAG_STABLE: false,
        MIRROR_BINARIES: false,
        SIGNING: false,
    ]

    // skip stages as indicated
    if (params.RESUME_FROM > '1.') {  // turns out '0.whatever' > '0'
        skip.PAYLOAD_CREATION = true
        skip.VERIFY_BUGS = true
        skip.TAG_STABLE = true
        skip.IMAGE_LIST = true
    }
    if (params.RESUME_FROM > '2.') {
        skip.MIRROR_BINARIES = true
    }
    if (params.RESUME_FROM > '3.') {
        skip.SIGNING = true
    }

    if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
        if (!params.ARCH || params.ARCH == "auto") {
            error("You must explicitly specify an ARCH to promote a release for a non-stream assembly.")
        }
        if (!params.VERSION) {
            error("You must explicitly specify a VERSION to promote a release for a non-stream assembly.")
        }
        (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.VERSION)
        group = "openshift-${major}.${minor}"
        // FIXME: Only support standard X.Y.Z and hotfix releases for now. RCs and FCs are not supported yet.
        release_config = buildlib.get_releases_config(group)?.releases?.get(params.ASSEMBLY)
        if (!release_config) {
            error("Assembly ${params.ASSEMBLY} is not defined in releases.yml.")
        }

        direct_release_nightly = !release.getAdvisories(group)?.image  // Whether this assembly should go through Errata process is determined by group config advisories.
        def release_type = release_config.assembly?.type?: "standard"  // Defaults to "standard" release if not specified
        switch(release_type) {
        case "standard":
            release_name = params.ASSEMBLY
            ga_release = true
            break
        case "custom":
            if (!params.RELEASE_OFFSET) {
                error("RELEASE_OFFSET is required when promoting a custom release payload. Use 0 if this is not a derivative of any GA named release.")
            }
            release_offset = params.RELEASE_OFFSET.toInteger()
            release_name = "${major}.${minor}.${release_offset}-assembly.${params.ASSEMBLY}"
            detect_previous = false
            is_4stable_release = false
            CLIENT_TYPE = 'ocp-dev-preview'  // Trigger beta2 key
            break
        case "candidate":
            is_prerelease = true
            release_name = "${major}.${minor}.0-${params.ASSEMBLY}"
            if (params.ASSEMBLY.startsWith('fc') {
                CLIENT_TYPE = 'ocp-dev-preview'  // Trigger beta2 key
            }
            break
        default:
            error("Unsupported release type $release_type")
        }
    } else {
        release_offset = params.RELEASE_OFFSET?params.RELEASE_OFFSET.toInteger():0
        (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.FROM_RELEASE_TAG)
        group = "openshift-${major}.${minor}"
        if (params.RELEASE_TYPE.startsWith('1.')) { // Standard X.Y.Z release
            release_name = "${major}.${minor}.${release_offset}"
            ga_release = true
        } else if (params.RELEASE_TYPE.startsWith('2.')) { // Release candidate (after code freeze)
            is_prerelease = true
            release_name = "${major}.${minor}.0-rc.${release_offset}"
        } else if (params.RELEASE_TYPE.startsWith('3.')) { // Feature candidate (around feature complete)
            is_prerelease = true
            direct_release_nightly = true
            release_name = "${major}.${minor}.0-fc.${release_offset}"
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
    }

    if (major > 3 && ga_release) {
        def next_minor = "${major}.${minor + 1}"
        if (!(commonlib.ocpReleaseState[next_minor] && commonlib.ocpReleaseState[next_minor]["release"])) {
            // Either next_minor is not yet defined, or its "release" is empty.
            next_is_prerelease = true
        }
    }

    slackChannel = slacklib.to(release_name)
    slackChannel.task("Public release prep for: ${release_name}${ params.DRY_RUN ? ' (DRY RUN)' : ''}") {
        taskThread ->

        stage("Check for Blocker Bugs") {
            if (!ga_release) {
                echo "Skip Blocker Bug check for FCs, RCs, and custom releases"
                return
            }
            commonlib.retrySkipAbort("Waiting for Blocker Bugs to be resolved", taskThread,
                                    "Blocker Bugs found for release; do not proceed without resolving. See https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#handling-blocker-bugs") {
                release.stageCheckBlockerBug(group)
            }
        }

        sshagent(['aos-cd-test']) {
            release_info = ""
            name = release_name
            def from_release_tag = null
            if (release_config) { // We are promoting a release for a non-stream assembly
                arch = params.ARCH
                priv = false  // should not contain embargoed content
                def reference_releases = release_config.assembly?.basis?.reference_releases?: [:]
                from_release_tag = reference_releases[arch]
            } else {
                from_release_tag = params.FROM_RELEASE_TAG.trim()
                // arch will fallback to params.ARCH if it is not part of the release name
                (arch, priv) = release.getReleaseTagArchPriv(from_release_tag)
            }

            RELEASE_STREAM_NAME = "4-stable${release.getArchPrivSuffix(arch, false)}"
            dest_release_tag = release.destReleaseTag(release_name, arch)

            description = params.DESCRIPTION
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0
            if (direct_release_nightly) {
                // Direct nightly releases can skip all advisory related steps.
                advisory = -1
            }
            String errata_url
            Map release_obj

            currentBuild.displayName = "${name} (${arch})"
            currentBuild.description = from_release_tag ? "${from_release_tag} -> ${release_name}" : release_name
            if (params.DRY_RUN) {
                currentBuild.displayName += " (dry-run)"
                currentBuild.description += "[DRY RUN]"
            }
            if (skip.PAYLOAD_CREATION) {
                currentBuild.displayName += " (skip payload creation)"
                currentBuild.description += "[SKIP PAYLOAD CREATION]"
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

            stage("get upgrade edges") {
                previousList = commonlib.parseList(params.PREVIOUS)
                if ( params.PREVIOUS.trim() == 'auto' && !skip.PAYLOAD_CREATION) {
                    taskThread.task('Gather PREVIOUS for release') {

                        if (!detect_previous) {
                            // Hotfixes don't get a PREVIOUS by default since we don't
                            // want customers upgrading to it unintentionally.
                            previousList = []
                            return
                        }

                        def acquire_failure = ''
                        def suggest_previous = ''
                        def in_flight_prev = ''
                        try {
                            suggest_previous = buildlib.doozer("release:calc-previous -a ${arch} --version ${release_name}", [capture: true])
                            echo "Doozer suggested: ${suggest_previous}"
                        } catch ( cincy_down ) {
                            acquire_failure = '****Doozer was not able to acquire data from Cincinnati. Inputs will need to be determined manually****. '
                            echo acquire_failure
                        }

                        prevMinor = minor - 1
                        in_flight_prev_required = true
                        if (params.IN_FLIGHT_PREV.toUpperCase() == 'SKIP') {
                            previousList = commonlib.parseList(suggest_previous)
                            print("Skipping asking for in_flight_prev")
                            in_flight_prev_required = false
                            in_flight_prev = ""
                        } else if (params.IN_FLIGHT_PREV) {
                            in_flight_prev = params.IN_FLIGHT_PREV.trim()
                            valid = release.validateInFlightPrevVersion(in_flight_prev, major, prevMinor)
                            if (valid) {
                                previousList = commonlib.parseList(suggest_previous) + commonlib.parseList(in_flight_prev)
                                print("Proceeding with given in_flight_prev: $in_flight_prev")
                                in_flight_prev_required = false
                            } else {
                                print("Error validating given in_flight_prev: $in_flight_prev . Asking for manual input")
                            }
                        }

                        if (in_flight_prev_required) {
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
                                in_flight_prev = resp.IN_FLIGHT_PREV
                                suggest_previous = resp.SUGGESTED
                                previousList = commonlib.parseList(suggest_previous) + commonlib.parseList(in_flight_prev)
                            }
                        }
                    }
                }
                previousList = previousList.toList().unique().sort()
                Collections.reverse(previousList)
                echo "previousList is ${previousList}"
            }

            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("add cve flaw bugs") {
                if ( params.SKIP_ATTACH_CVE_FLAWS ) {
                    echo "skipping attach cve flaws step"
                    return
                }
                if (advisory == -1) {
                    return
                }
                if (major == 4 && !is_4stable_release) {
                    return
                }
                release.getAdvisories(group).each {
                    commonlib.retrySkipAbort("Add CVE flaw bugs", taskThread, "Error attaching CVE flaw bugs") {
                        commonlib.shell(
                            script: "${buildlib.ELLIOTT_BIN} --group ${group} --assembly ${params.ASSEMBLY ?: 'stream'} attach-cve-flaws --advisory ${it.value} ${params.DRY_RUN ? '--dry-run' : ''}",
                        )
                    }
                }
            }
            stage("validation") {
                if (advisory == -1) {
                    // No advisory dance
                    errata_url = ''
                    return
                }
                skipVerifyBugs = !ga_release || next_is_prerelease || skip.VERIFY_BUGS
                commonlib.retrySkipAbort("Validating release", taskThread, "Error running release validation") {
                    def retval = release.stageValidation(quay_url, dest_release_tag, advisory, params.PERMIT_PAYLOAD_OVERWRITE, params.PERMIT_ALL_ADVISORY_STATES, from_release_tag, arch, skipVerifyBugs, skip.PAYLOAD_CREATION)
                    advisory = advisory ?: retval.advisoryInfo.id
                    errata_url = retval.errataUrl
                }
            }
            stage("build payload") {
                if (skip.PAYLOAD_CREATION) {
                    echo "Don't actually create the payload because SKIP_PAYLOAD_CREATION is set."
                    return
                }
                release.stageGenPayload(quay_url, release_name, dest_release_tag, from_release_tag, description, previousList.join(','), errata_url)
            }

            stage("tag stable") {
                if (skip.TAG_STABLE) {
                    echo "Do not tag stable because SKIP_TAG_STABLE is set."
                    return
                }
                if (!is_4stable_release) {
                    // Something like a hotfix should not go into 4-stable in the release controller
                    return
                }
                release.stageTagRelease(quay_url, release_name, dest_release_tag, arch)
            }

            stage("request upgrade tests") {
                if (skip.PAYLOAD_CREATION) {
                    echo "Don't request upgrade tests because SKIP_PAYLOAD_CREATION flag is set."
                    return
                }
                if (direct_release_nightly || !is_4stable_release || arch != 'x86_64') {
                    // For a hotfix, speed is our goal. Assume testing has already been done.
                    // For an FC, we are so early in the release cycle that non-default upgrade tests are
                    // only noise.
                    // Skip for non x64 arches because we don't test for that.
                    return
                }
                try {  // don't let a slack outage break the job at this point
                    def modeOptions = [ 'aws', 'gcp', 'azure' ]
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
                if (arch != 'x86_64') {
                    echo "No need to send docs an image list for non-x86_64 releases."
                    return
                }
                if (advisory == -1) {
                    echo "Skipping image list for dummy advisory."
                    return
                }
                if (skip.IMAGE_LIST) {
                    currentBuild.description += "[No image list]"
                    return
                }
                try {
                    filename = "${dest_release_tag}-image-list.txt"
                    retry (3) {
                        commonlib.shell(script: "${buildlib.ELLIOTT_BIN} advisory-images -a ${advisory} > ${filename}")
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

            stage("mirror binaries") {
                if (skip.MIRROR_BINARIES) {
                    echo "Don't mirror binaries because we're resuming later in the job."
                    return
                }
                retry(3) {
                    release.stagePublishClient(quay_url, dest_release_tag, release_name, arch, CLIENT_TYPE)
                }
            }

            stage("sync RHCOS") {
                if (!is_prerelease) {
                    echo "Skipping rhcos sync"
                    return
                }

                suffix = release.getArchPrivSuffix(arch, false)
                tag = from_release_tag

                cmd = "oc image info -o json \$(oc adm release info --image-for machine-os-content registry.ci.openshift.org/ocp$suffix/release$suffix:$tag) | jq -r .config.config.Labels.version"
                rhcos_build =  commonlib.shell(
                    returnStdout: true,
                    script: cmd
                ).trim()
                print("RHCOS build: $rhcos_build")

                rhcos_mirror_prefix = is_prerelease ? "pre-release" : "$major.$minor"

                sync_params = [
                    buildlib.param('String','BUILD_VERSION', "$major.$minor"),
                    buildlib.param('String','NAME', release_name),
                    buildlib.param('String','ARCH', arch),
                    buildlib.param('String','RHCOS_MIRROR_PREFIX', rhcos_mirror_prefix),
                    buildlib.param('String','RHCOS_BUILD', rhcos_build),
                    booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
                    booleanParam(name: 'MOCK', value: params.MOCK)
                ]

                build(
                    job: '/aos-cd-builds/build%252Frhcos_sync',
                    propagate: false,
                    parameters: sync_params
                )
            }

            stage("send release message") {
                if (!is_4stable_release) {
                    echo "Not a stable release, not sending message over bus"
                    return
                }
                if (params.DRY_RUN) {
                    echo "DRY_RUN: Not sending release message"
                    return
                }
                if (skip.SIGNING) {
                    echo "Don't send another release message because we're resuming later in the job."
                    return
                }
                release.sendReleaseCompleteMessage(release_obj, advisory, errata_url, arch)
            }

            stage("sign artifacts") {
                if (skip.PAYLOAD_CREATION) {
                    payloadDigest = release.getPayloadDigest(quay_url, dest_release_tag)
                }
                if (skip.SIGNING) {
                    echo "Don't do the signing because we're resuming later in the job."
                    return
                }
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
                if (!is_4stable_release) {
                    echo "Skipping PR creation for custom (hotfix) release."
                    return
                }
                if (arch == 'x86_64' || params.OPEN_NON_X86_PR ) {
                    commonlib.retrySkipAbort('Open Cincinnati PRs', taskThread) {
                        build(
                                job: '/aos-cd-builds/build%2Fcincinnati-prs',  propagate: true,
                                parameters: [
                                    buildlib.param('String', 'FROM_RELEASE_TAG', from_release_tag),
                                    buildlib.param('String', 'RELEASE_NAME', release_name),
                                    buildlib.param('String', 'ADVISORY_NUM', "${advisory}"),
                                    booleanParam(name: 'CANDIDATE_CHANNEL_ONLY', value: true),
                                    buildlib.param('String', 'GITHUB_ORG', 'openshift'),
                                    booleanParam(name: 'SKIP_OTA_SLACK_NOTIFICATION', value: params.SKIP_OTA_SLACK_NOTIFICATION)
                                ]
                        )
                    }
                } else {
                    echo "Skipping PR creation for non-x86 CPU arch"
                }
            }

            stage("validate RHSAs") {
                if (params.DRY_RUN) {
                    return
                }
                if (advisory == -1) {
                    return
                }
                if (major == 4 && !is_4stable_release) {
                    return
                }
                release.getAdvisories(group).each {
                    advisory_id = "${it.value}"
                    res = commonlib.shell(
                        script: "${buildlib.ELLIOTT_BIN} validate-rhsa ${advisory_id}",
                        returnAll: true,
                    )
                    if (res.returnStatus != 0) {
                        msg = """
                            Review of CVE situation required for advisory <https://errata.devel.redhat.com/advisory/${advisory_id}|${advisory_id}>.
                            Report:
                            ```
                            ${res.stdout}
                            ```
                            Note: For GA image advisories this is expected to fail.
                        """.stripIndent()
                        slacklib.to(version).say(msg)
                    }
                }
            }
        }

        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}
        releaseArch = commonlib.goArchForBrewArch(arch)
        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${release_name} (${arch})",
            body: """
Jenkins Job: ${env.BUILD_URL}
Release Page: https://${releaseArch}.ocp.releases.ci.openshift.org/releasestream/4-stable${release.getArchPrivSuffix(arch, false)}/release/${release_name}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${dest_release_tag}

${release_info}
        """);
        buildlib.cleanWorkspace()
    }
}
