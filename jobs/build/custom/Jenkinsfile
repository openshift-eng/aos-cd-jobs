node {
    checkout scm

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
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
                    [
                        name: 'VERSION',
                        description: '(Optional) version for build (e.g. 4.1.0) instead of most recent\nor "+" to bump most recent version',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'RELEASE',
                        description: '(Optional) Release string for build instead of default (1 for 3.x, timestamp for 4.x)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'RPMS',
                        description: 'CSV list of RPMs to build. Empty for all. Enter "NONE" to not build any.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "NONE"
                    ],
                    [
                        name: 'IMAGES',
                        description: 'CSV list of images to build. Empty for all. Enter "NONE" to not build any.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'EXCLUDE_IMAGES',
                        description: 'CSV list of images to skip building (IMAGES value is ignored)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'IMAGE_MODE',
                        description: 'How to update image dist-gits: with a source rebase, just dockerfile updates, or not at all (no version/release update)',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: ['rebase', 'update-dockerfile', 'nothing'].join('\n'),
                        defaultValue: 'images:rebase',
                    ],
                    [
                        name: 'DOOZER_DATA_PATH',
                        description: '(Optional) you may override with your fork',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "https://github.com/openshift/ocp-build-data"
                    ],
                    [
                        name: 'SIGNED',
                        description: 'Build images against signed RPMs?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: true
                    ],
                    [
                        name: 'SWEEP_BUGS',
                        description: 'Sweep and attach bugs to advisories',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "",
                    ],
                    [
                        name: 'IMAGE_ADVISORY_ID',
                        description: 'Advisory Number to attach new images to. \'default\' use number from ocp-build-data, leave it empty if you do not want add',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "",
                    ],
                    [
                        name: 'RPM_ADVISORY_ID',
                        description: 'Advisory Number to attach new rpms to. \'default\' use number from ocp-build-data, leave it empty if you do not want add',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "",
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-custom-build@redhat.com',
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

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
                    command += "rpms:build --version ${version} --release ${release} "
                    if (params.IGNORE_LOCKS) {
                         buildlib.doozer command
                    } else {
                        lock("github-activity-lock-${params.BUILD_VERSION}") { buildlib.doozer command }
                    }
                }
            }

            stage("puddle: ose 'building'") {
                if (rpms.toUpperCase() != "NONE") {
                    lock("compose-lock-${params.BUILD_VERSION}") {  // note: respect puddle lock regardless of IGNORE_LOCKS
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
                command += "images:${params.IMAGE_MODE} --version v${version} --release ${release} "
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
    }
}
