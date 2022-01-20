#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    commonlib.describeJob("⛔❌⛔ multi_promote (deprecated) ⛔❌⛔ ", """
        <b>Deprecated. Use <a href="/job/aos-cd-builds/job/build%252Fpromote-assembly/">promote-assembly</a> instead</b>

        <h2>Kick off multiple promote jobs for selected nightlies</h2>
    """)


    def doozer_working = "${WORKSPACE}/doozer_working"

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '7',
                    daysToKeepStr: '7'
                )
            ),
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
                    string(
                        name: "NIGHTLIES",
                        description: "List of proposed nightlies for each arch, separated by comma. Do not specify for a non-stream assembly.",
                        trim: true
                    ),
                    string(
                        name: 'RELEASE_OFFSET',
                        description: 'Integer. Do not specify for standard or candidate assembly. If offset is X for 4.5 nightly => Release name is 4.5.X for standard, 4.5.0-rc.X for Release Candidate, 4.5.0-fc.X for Feature Candidate, 4.5.X-assembly.ASSEMBLY_NAME for custom release',
                        trim: true,
                    ),
                    string(
                        name: 'IN_FLIGHT_PREV',
                        description: 'This is the in flight release version of previous minor version of OCP. Leave blank to be prompted later in the job. "skip" to indicate that there is no such release in flight. Used to fill upgrade suggestions.',
                        defaultValue: "",
                        trim: true,
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
                        description: 'Skip cincinnati PR creation',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'PERMIT_ALL_ADVISORY_STATES',
                        description: 'DO NOT USE without team lead approval. Allows "Standard" promotion when advisory is not in QE state.',
                        defaultValue: false,
                    ),
                    commonlib.dryrunParam('Take no actions. Note: still notifies and runs signing job (which fails)'),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    String[] nightly_list = []

    def (major, minor) = [0, 0]
    //commonlib.ocpReleaseState
    if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
        version = params.VERSION
        if (!version) {
            error("You must explicitly specify a VERSION to promote a release for a non-stream assembly.")
        }
        (major, minor) = commonlib.extractMajorMinorVersionNumbers(version)
        currentBuild.displayName = "${version}: assembly ${params.ASSEMBLY}"
    } else {
        // some basic validations
        if (!params.NIGHTLIES) {
            error("You must provide a list of proposed nightlies.")
        }
        nightly_list = params.NIGHTLIES.split("[,\\s]+")
        versions = nightly_list.collect{ commonlib.extractMajorMinorVersionNumbers(it) }
        if (versions.toSet().size() != 1) {
            error("Nightlies belong to different OCP versions.")
        }
        (major, minor) = versions[0]
        release_offset = params.RELEASE_OFFSET?params.RELEASE_OFFSET.toInteger():0
        if (params.RELEASE_TYPE.startsWith('1.')) { // Standard X.Y.Z release
            release_name = "${major}.${minor}.${release_offset}"
        } else if (params.RELEASE_TYPE.startsWith('2.')) { // Release candidate (after code freeze)
            release_name = "${major}.${minor}.0-rc.${release_offset}"
        } else if (params.RELEASE_TYPE.startsWith('3.')) { // Feature candidate (around feature complete)
            release_name = "${major}.${minor}.0-fc.${release_offset}"
        } else if (params.RELEASE_TYPE.startsWith('4.')) {   // Hotfix for a specific customer
            // ignore offset. Release is named same as nightly but with 'hotfix' instead of 'nightly'.
            release_name = params.FROM_RELEASE_TAG.trim().replaceAll('nightly', 'hotfix')
        }
        currentBuild.displayName = release_name
    }

    def arches = commonlib.ocpReleaseState["${major}.${minor}"]?.release
    if (!arches) {
        arches = commonlib.ocpReleaseState["${major}.${minor}"]?."pre-release"
        if (!arches) {
            error("Could not find arches for OCP version :( Make sure they are specified in commonlib.ocpReleaseState: $commonlib.ocpReleaseState")
        }
    }

    def archNightlyMap = nightly_list.collectEntries {[release.getReleaseTagArchPriv(it)[0], it]}  // key is arch, value is nightly

    if (nightly_list) {
        // Assert nightly_list is complete
        if (archNightlyMap.keySet() != arches.toSet()) {
            def resp = input(
                message: "Something doesn't seem right. Job expects one nightly of each arch. Do you still want to proceed with given nightlies $nightly_list?",
                parameters: [
                    booleanParam(
                        name: 'PROCEED',
                        defaultValue: false,
                        description: "Are you sure to proceed with the given nightlies?"
                    )
                ]
            )
            if (!resp) {
                error("Aborting.")
            }
        }
    }

    common_params = [
        buildlib.param('String','VERSION', params.VERSION),
        buildlib.param('String','ASSEMBLY', params.ASSEMBLY),
        buildlib.param('String','RELEASE_TYPE', params.RELEASE_TYPE),
        buildlib.param('String','RELEASE_OFFSET', params.RELEASE_OFFSET),
        buildlib.param('String','IN_FLIGHT_PREV', params.IN_FLIGHT_PREV),
        buildlib.param('String','RESUME_FROM', params.RESUME_FROM),
        buildlib.param('String','ADVISORY', ""),
        booleanParam(name: 'SKIP_ATTACH_CVE_FLAWS', value: params.SKIP_ATTACH_CVE_FLAWS),
        booleanParam(name: 'SKIP_CINCINNATI_PR_CREATION', value: params.SKIP_CINCINNATI_PR_CREATION),
        booleanParam(name: 'PERMIT_ALL_ADVISORY_STATES', value: params.PERMIT_ALL_ADVISORY_STATES),
        booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
        booleanParam(name: 'MOCK', value: params.MOCK)
    ]

    promote_job_location = 'build%2Fpromote'
    parallel(arches.collectEntries { arch ->
        [arch, {
            stage(arch) {
                    def params = common_params.clone()
                    nightly = archNightlyMap[arch]
                    params << buildlib.param('String','FROM_RELEASE_TAG', nightly?: "")
                    params << buildlib.param('String','ARCH', arch)

                    build(
                        job: promote_job_location,
                        propagate: true,
                        parameters: params
                    )
                    currentBuild.description += "<br>triggered promote: ${arch}"
            }
        }]
    })

    buildlib.cleanWorkspace()
}
