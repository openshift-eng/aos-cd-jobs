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
                    commonlib.doozerParam(),
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
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to rebase & build for. If assemblies are not enabled in group.yml, this parameter will be ignored',
                        defaultValue: "test",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'RPMS',
                        description: 'List of RPM distgits to build. Empty for all. Enter "NONE" to not build any.',
                        defaultValue: "NONE",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'UPDATE_REPOS',
                        description: 'Build plashets (always true if building RPMs or images for non-stream assembly)',
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
                        description: 'How to update image dist-gits: with a source rebase, or not at all (re-run as-is)',
                        choices: ['rebase', 'nothing'].join('\n'),
                    ),
                    booleanParam(
                        name: 'SCRATCH',
                        description: 'Run scratch builds (only unrelated images, no children)',
                        defaultValue: false,
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
    buildlib.initialize(false, true, params.BUILD_VERSION == "3.11")

    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    def doozer_data_path = params.DOOZER_DATA_PATH
    def (majorVersion, minorVersion) = commonlib.extractMajorMinorVersionNumbers(params.BUILD_VERSION)
    def groupParam = "openshift-${params.BUILD_VERSION}"
    def doozer_data_gitref = params.DOOZER_DATA_GITREF
    if (doozer_data_gitref) {
        groupParam += "@${params.DOOZER_DATA_GITREF}"
    }
    def doozerOpts = "--working-dir ${doozer_working} --data-path ${doozer_data_path} --group '${groupParam}' "
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

    if (params.ASSEMBLY && params.ASSEMBLY != 'stream' && buildlib.doozer("${doozerOpts} config:read-group --default=False assemblies.enabled", [capture: true]).trim() != 'True') {
        error("ASSEMBLY cannot be set to '${params.ASSEMBLY}' because assemblies are not enabled in ocp-build-data.")
    }

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
                if (params.UPDATE_REPOS || (images.toUpperCase() != "NONE" && params.ASSEMBLY && params.ASSEMBLY != 'stream') || rpms.toUpperCase() != "NONE") {
                    lock("update-repo-lock-${params.BUILD_VERSION}") {  // note: respect repo lock regardless of IGNORE_LOCKS

                        buildlib.build_plashets(doozerOpts, version, release)
                        if ("${majorVersion}" == "4" && buildlib.getAutomationState(doozerOpts) in ["scheduled", "yes", "True"]) {
                            slacklib.to(params.BUILD_VERSION).say(params.UPDATE_REPOS ?
                                """ *:alert: custom build repositories update ran during automation freeze*
                                    UPDATE_REPOS parameter was set to true, forcing a repo update during automation freeze."""
                                :
                                """*:alert: custom build repositories ran during automation freeze*
                                    RPM rebuild(s) in the build plan forced a repo update during automation freeze."""
                            )
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
                command = "${base_command} images:build --push-to-defaults ${params.SCRATCH ? '--scratch' : ''}"
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
                if (params.SCRATCH || !any_images_to_build) { return }  // no point
                if (majorVersion >= 4) {
                    def record_log = buildlib.parse_record_log(doozer_working)
                    def records = record_log.get('build', [])
                    def operator_nvrs = []
                    for (record in records) {
                        if (record["has_olm_bundle"] != '1' || record['status'] != '0' || !record["nvrs"]) {
                            continue
                        }
                        operator_nvrs << record["nvrs"].split(",")[0]
                    }
                    buildlib.sync_images(
                        majorVersion,
                        minorVersion,
                        "aos-team-art@redhat.com", // "reply to"
                        params.ASSEMBLY,
                        operator_nvrs,
                        doozer_data_path,
                        doozer_data_gitref
                    )
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
