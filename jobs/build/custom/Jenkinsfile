node {
    checkout scm

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("custom", """
        <h2>Run component builds in ways other jobs can't</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.

        This job is mainly used when you need something specific not handled
        well by the ocp3 or ocp4 jobs and don't want to set up and use doozer.

        It is also still necessary for building OCP 3.11 releases using signed
        RPMs in containers.

        For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/custom/README.md" target="_blank">README</a>
    """)


    // Please update README.md if modifying parameter names or semantics
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
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    booleanParam(
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        defaultValue: false
                    ),
                    string(
                        name: 'VERSION',
                        description: '(Optional) version for build (e.g. 4.3.42) instead of most recent\nor "+" to bump most recent version',
                    ),
                    string(
                        name: 'RELEASE',
                        description: '(Optional) Release string for build instead of default (1 for 3.x, timestamp.p? for 4.x)',
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift/ocp-build-data"
                    ),
                    string(
                        name: 'RPMS',
                        description: 'List of RPM distgits to build. Empty for all. Enter "NONE" to not build any.',
                        defaultValue: "NONE"
                    ),
                    booleanParam(
                        name: 'COMPOSE',
                        description: 'Build plashets/compose (always true if building RPMs)',
                        defaultValue: false
                    ),
                    string(
                        name: 'IMAGES',
                        description: 'List of image distgits to build. Empty for all. Enter "NONE" to not build any.',
                    ),
                    string(
                        name: 'EXCLUDE_IMAGES',
                        description: 'List of image distgits NOT to build (builds all not listed - IMAGES value is ignored)',
                    ),
                    choice(
                        name: 'IMAGE_MODE',
                        description: 'How to update image dist-gits: with a source rebase, just dockerfile updates, or not at all (no version/release update)',
                        choices: ['rebase', 'update-dockerfile', 'nothing'].join('\n'),
                    ),
                    booleanParam(
                        name: 'SIGNED',
                        description: '(3.11) Build images against signed RPMs?',
                        defaultValue: true
                    ),
                    booleanParam(
                        name: 'SWEEP_BUGS',
                        description: 'Sweep and attach bugs to advisories',
                        defaultValue: false
                    ),
                    string(
                        name: 'IMAGE_ADVISORY_ID',
                        description: 'Advisory id for attaching new images if desired. Enter "default" to use current advisory from ocp-build-data',
                    ),
                    string(
                        name: 'RPM_ADVISORY_ID',
                        description: 'Advisory id for attaching new rpms if desired. Enter "default" to use current advisory from ocp-build-data',
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List',
                        defaultValue: "",
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-custom-build@redhat.com',
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )   // Please update README.md if modifying parameter names or semantics
    buildlib.initialize()

    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    def doozer_data_path = params.DOOZER_DATA_PATH
    def majorVersion = params.BUILD_VERSION.split('\\.')[0]
    def minorVersion = params.BUILD_VERSION.split('\\.')[1]
    def doozerOpts = "--working-dir ${doozer_working} --data-path ${doozer_data_path} --group 'openshift-${params.BUILD_VERSION}' "
    def version = params.BUILD_VERSION
    def release = "?"
    if (params.IMAGE_MODE != "nothing") {
        version = buildlib.determineBuildVersion(params.BUILD_VERSION, buildlib.getGroupBranch(doozerOpts), params.VERSION)
        release = params.RELEASE.trim() ?: buildlib.defaultReleaseFor(params.BUILD_VERSION)
    }
    def repo_type = params.SIGNED ? "signed" : "unsigned"
    def images = commonlib.cleanCommaList(params.IMAGES)
    def exclude_images = commonlib.cleanCommaList(params.EXCLUDE_IMAGES)
    def rpms = commonlib.cleanCommaList(params.RPMS)


    currentBuild.displayName = "#${currentBuild.number} - ${version}-${release}"

    try {
        sshagent(["openshift-bot"]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot
            currentBuild.description = ""

            stage("rpm builds") {
                if (rpms.toUpperCase() != "NONE") {
                    currentBuild.displayName += rpms.contains(",") ? " [RPMs]" : " [${rpms} RPM]"
                    currentBuild.description = "building RPM(s): ${rpms}\n"
                    command = doozerOpts
                    if (rpms) { command += "-r '${rpms}' " }
                    command += "rpms:build --version ${version} --release '${release}' "

                    def buildRpms = { ->
                        buildlib.doozer command
                        def rpmList = rpms.split(",")
                        // given this may run without locks, don't blindly rebuild for el8 unless building for el7
                        if (rpmList.contains("openshift") || rpmList.contains("openshift-clients") || !rpmList) {
                            build(
                                job: "build%2Fel8-rebuilds",
                                propagate: true,
                                parameters: [
                                    string(name: "BUILD_VERSION", value: params.BUILD_VERSION),
                                    booleanParam(name: "MOCK", value: false),
                                ],
                            )
                        }
                    }
                    params.IGNORE_LOCKS ?  buildRpms() : lock("github-activity-lock-${params.BUILD_VERSION}") { buildRpms() }
                }
            }

            stage("repo: ose 'building'") {
                if (params.COMPOSE || rpms.toUpperCase() != "NONE") {
                    lock("compose-lock-${params.BUILD_VERSION}") {  // note: respect puddle lock regardless of IGNORE_LOCKS
                        if ("${majorVersion}" == "3") {
                            echo 'Building 3.x puddle'
                            aosCdJobsCommitSha = commonlib.shell(
                                    returnStdout: true,
                                    script: "git rev-parse HEAD",
                            ).trim()
                            puddleConfBase = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${aosCdJobsCommitSha}/build-scripts/puddle-conf"
                            puddleConf = "${puddleConfBase}/atomic_openshift-${params.BUILD_VERSION}.conf"
                            buildlib.build_puddle(
                                    puddleConf,    // The puddle configuration file to use
                                    null, // openshifthosted key
                                    "-b",   // do not fail if we are missing dependencies
                                    "-d",   // print debug information
                                    "-n",   // do not send an email for this puddle
                                    "-s",   // do not create a "latest" link since this puddle is for building images
                                    "--label=building"   // create a symlink named "building" for the puddle
                            )
                        } else {
                            echo 'Building 4.x plashet'
                            // For 4.x, use plashets
                            buildlib.buildBuildingPlashet(version, release, 8, true)  // build el8 embargoed plashet
                            buildlib.buildBuildingPlashet(version, release, 7, true)  // build el7 embargoed plashet
                            buildlib.buildBuildingPlashet(version, release, 8, false)  // build el8 unembargoed plashet
                            buildlib.buildBuildingPlashet(version, release, 7, false)  // build el7 unembargoed plashet
                        }
                    }
                }
            }

            // determine which images, if any, should be built, and how to tell doozer that
            include_exclude = ""
            any_images_to_build = true
            if (exclude_images) {
                include_exclude = "-x ${exclude_images}"
                currentBuild.displayName += " [images]"
            } else if (images.toUpperCase() == "NONE") {
                any_images_to_build = false
            } else if (images) {
                include_exclude = "-i ${images}"
                currentBuild.displayName += images.contains(",") ? " [images]" : " [${images} image]"
            }

            stage("update dist-git") {
                if (!any_images_to_build) { return }
                if (params.IMAGE_MODE == "nothing") { return }

                currentBuild.description += "building image(s): ${include_exclude ?: 'all'}"
                command = doozerOpts
                command += "--latest-parent-version ${include_exclude} "
                command += "images:${params.IMAGE_MODE} --version v${version} --release '${release}' "
                command += "--repo-type ${repo_type} "
                command += "--message 'Updating Dockerfile version and release ${version}-${release}' --push "
                if (params.IGNORE_LOCKS) {
                     buildlib.doozer command
                } else {
                    lock("github-activity-lock-${params.BUILD_VERSION}") { buildlib.doozer command }
                }
            }

            stage("build images") {
                if (!any_images_to_build) { return }
                command = doozerOpts
                command += "${include_exclude} --profile ${repo_type} images:build --push-to-defaults"
                try {
                    buildlib.doozer command
                } catch (err) {
                    def record_log = buildlib.parse_record_log(doozer_working)
                    def failed_map = buildlib.get_failed_builds(record_log, true)
                    if (failed_map) {
                        def r = buildlib.determine_build_failure_ratio(record_log)
                        if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
                            echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
                        } else {
                            buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
                        }
                    }
                    throw err  // build is considered failed if anything failed
                }
            }

            stage('sync images') {
                if (majorVersion == "4") {
                    buildlib.sync_images(
                        majorVersion,
                        minorVersion,
                        "aos-team-art@redhat.com", // "reply to"
                        currentBuild.number
                    )
                }
            }

            stage ('Attach Images') {
                if (params.IMAGE_ADVISORY_ID != "") {
                    def attach = params.IMAGE_ADVISORY_ID == "default" ? "--use-default-advisory image" : "--attach ${params.IMAGE_ADVISORY_ID}"
                    buildlib.elliott """
                    --data-path ${doozer_data_path}
                    --group 'openshift-${majorVersion}.${minorVersion}'
                    find-builds
                    --kind image
                    ${attach}
                    """
                }

                if (params.RPM_ADVISORY_ID != "") {
                    def attach = params.RPM_ADVISORY_ID == "default" ? "--use-default-advisory rpm" : "--attach ${params.RPM_ADVISORY_ID}"
                    buildlib.elliott """
                    --data-path ${doozer_data_path}
                    --group 'openshift-${majorVersion}.${minorVersion}'
                    find-builds
                    --kind rpm
                    ${attach}
                    """
                }
            }

            stage('sweep') {
                if (params.SWEEP_BUGS) {
                    buildlib.sweep(params.BUILD_VERSION, false)
                }
            }

            if (params.MAIL_LIST_SUCCESS.trim()) {
                commonlib.email(
                    to: params.MAIL_LIST_SUCCESS,
                    from: "aos-team-art@redhat.com",
                    subject: "Successful custom OCP build: ${currentBuild.displayName}",
                    body: "Jenkins job: ${commonlib.buildURL()}\n${currentBuild.description}",
                )
            }
        }
    } catch (err) {
        currentBuild.description += "\nerror: ${err.getMessage()}"
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Error building custom OCP: ${currentBuild.displayName}",
            body: """Encountered an error while running OCP pipeline:

${currentBuild.description}

Jenkins job: ${commonlib.buildURL()}
Job console: ${commonlib.buildURL('console')}
    """)

        currentBuild.result = "FAILURE"
        throw err
    } finally {
        commonlib.safeArchiveArtifacts([
                "doozer_working/*.log",
                "doozer_working/*.yaml",
                "doozer_working/brew-logs/**",
            ])
        buildlib.cleanWorkdir(doozer_working)
    }
}
