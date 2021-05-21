node {
    checkout scm

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
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
                    daysToKeepStr: '365',
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
                        trim: true,
                    ),
                    string(
                        name: 'RELEASE',
                        description: '(Optional) Release string for build instead of default (1 for 3.x, timestamp.p? for 4.x)',
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'RPMS',
                        description: 'List of RPM distgits to build. Empty for all. Enter "NONE" to not build any.',
                        defaultValue: "NONE",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'COMPOSE',
                        description: 'Build plashets/compose (always true if building RPMs)',
                        defaultValue: false,
                    ),
                    string(
                        name: 'IMAGES',
                        description: 'List of image distgits to build. Empty for all. Enter "NONE" to not build any.',
                        trim: true,
                    ),
                    string(
                        name: 'EXCLUDE_IMAGES',
                        description: 'List of image distgits NOT to build (builds all not listed - IMAGES value is ignored)',
                        trim: true
                    ),
                    choice(
                        name: 'IMAGE_MODE',
                        description: 'How to update image dist-gits: with a source rebase, or not at all (no version/release update)',
                        choices: ['rebase', 'nothing'].join('\n'),
                    ),
                    booleanParam(
                        name: 'SCRATCH',
                        description: 'Run scratch builds (only unrelated images, no children)',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SWEEP_BUGS',
                        description: 'Sweep and attach bugs to advisories',
                        defaultValue: false,
                    ),
                    string(
                        name: 'IMAGE_ADVISORY_ID',
                        description: 'Advisory id for attaching new images if desired. Enter "default" to use current advisory from ocp-build-data',
                        trim: true
                    ),
                    string(
                        name: 'RPM_ADVISORY_ID',
                        description: 'Advisory id for attaching new rpms if desired. Enter "default" to use current advisory from ocp-build-data',
                        trim: true,
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-custom-build@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )   // Please update README.md if modifying parameter names or semantics
    buildlib.initialize()

    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    def doozer_data_path = params.DOOZER_DATA_PATH
    def (majorVersion, minorVersion) = commonlib.extractMajorMinorVersionNumbers(params.BUILD_VERSION)
    def doozerOpts = "--working-dir ${doozer_working} --data-path ${doozer_data_path} --group 'openshift-${params.BUILD_VERSION}' "
    def version = params.BUILD_VERSION
    def release = "?"
    if (params.IMAGE_MODE != "nothing") {
        version = buildlib.determineBuildVersion(params.BUILD_VERSION, buildlib.getGroupBranch(doozerOpts), params.VERSION)
        release = params.RELEASE.trim() ?: buildlib.defaultReleaseFor(params.BUILD_VERSION)
    }
    // If any arch is ready for GA, use signed repos for all (plashets will sign everything).
    def repo_type = commonlib.ocpReleaseState[params.BUILD_VERSION]['release'] ? 'signed' : 'unsigned'

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
                    command += "rpms:rebase-and-build --version ${version} --release '${release}' ${params.SCRATCH ? '--scratch' : ''} "

                    def buildRpms = { ->
                        buildlib.doozer command
                    }
                    params.IGNORE_LOCKS ?  buildRpms() : lock("github-activity-lock-${params.BUILD_VERSION}") { buildRpms() }
                }
            }

            stage("repo: ose 'building'") {
                if (params.COMPOSE || rpms.toUpperCase() != "NONE") {
                    lock("compose-lock-${params.BUILD_VERSION}") {  // note: respect puddle lock regardless of IGNORE_LOCKS
                        def auto_signing_advisory = Integer.parseInt(buildlib.doozer("${doozerOpts} config:read-group --default=0 signing_advisory", [capture: true]).trim())
                        echo 'Building plashet'
                        buildlib.buildBuildingPlashet(version, release, 7, true, auto_signing_advisory)  // build el7 embargoed plashet
                        buildlib.buildBuildingPlashet(version, release, 7, false, auto_signing_advisory)  // build el7 unembargoed plashet
                        if ("${majorVersion}" == "4") {
                            buildlib.buildBuildingPlashet(version, release, 8, true, auto_signing_advisory)  // build el8 embargoed plashet
                            buildlib.buildBuildingPlashet(version, release, 8, false, auto_signing_advisory)  // build el8 unembargoed plashet

                            if(params.COMPOSE)
                                notificationMessage = """
                                    *:alert: custom ocp4 build compose ran during automation freeze*
                                    COMPOSE parameter was set to true that forced build compose during automation freeze."""
                            else
                                notificationMessage = """
                                    *:alert: custom ocp4 build compose ran during automation freeze*
                                    There were RPMs in the build plan that forced build compose during automation freeze."""

                            slacklib.to(params.BUILD_VERSION).say(notificationMessage)

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
                base_command = "${doozerOpts} ${include_exclude} --profile ${repo_type}"
                command = "${base_command} images:build ${params.SCRATCH ? '--scratch' : ''}"
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

            stage('push images to qe quay') {
                if (params.SCRATCH || !any_images_to_build) { return }  // no point
                base_command = "${doozerOpts} ${include_exclude} --profile ${repo_type}"
                command = "${base_command} images:push --to-defaults"
                if (majorVersion == 4) {
                    command += " --filter-by-os='.*'"  // full multi-arch sync
                }
                try {
                    buildlib.doozer command
                } catch (err) {
                    currentBuild.description += "\n<br>image push to qe quay did not completely succeed"
                    currentBuild.result = "UNSTABLE"
                }
            }

            stage('sync images') {
                if (params.SCRATCH || !any_images_to_build) { return }  // no point
                if (majorVersion == 4) {
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
                    buildlib.sweep(params.BUILD_VERSION)
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
        commonlib.compressBrewLogs()
        commonlib.safeArchiveArtifacts([
                "doozer_working/*.log",
                "doozer_working/*.yaml",
                "doozer_working/brew-logs/**",
            ])
        buildlib.cleanWorkdir(doozer_working)
        buildlib.cleanWorkspace()
    }
}
