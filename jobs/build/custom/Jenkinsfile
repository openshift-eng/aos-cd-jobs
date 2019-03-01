node {
    checkout scm
    def commonlib = load("pipeline-scripts/commonlib.groovy")

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '1000')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    [
                        name: 'VERSION',
                        description: 'Version string for build (e.g. 4.0.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'RELEASE',
                        description: 'Release string for build',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'SKIP_OSE',
                        description: 'If certain the ose repo is not needed, save minutes by not cloning it.',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
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
                        name: 'SIGNED',
                        description: 'Build images against signed RPMs?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-team-art@redhat.com',
                        ].join(',')
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-team-art@redhat.com',
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)
    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    master_ver = commonlib.ocpDefaultVersion
    version = commonlib.standardVersion(params.VERSION)
    release = params.RELEASE.trim()
    repo_type = params.SIGNED ? "signed" : "unsigned"
    images = commonlib.cleanCommaList(params.IMAGES)
    exclude_images = commonlib.cleanCommaList(params.EXCLUDE_IMAGES)
    rpms = commonlib.cleanCommaList(params.RPMS)

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    doozer_working = "${WORKSPACE}/doozer_working"
    //Clear out previous workspace
    sh "rm -rf ${doozer_working}"
    sh "mkdir -p ${doozer_working}"


    currentBuild.displayName = "#${currentBuild.number} - ${version}-${release}"

    try {
        sshagent(["openshift-bot"]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot

            // Some images require OSE as a source.
            // Instead of trying to figure out which do, always clone
            stage("ose repo") {
                if (params.SKIP_OSE) { return }
                currentBuild.description = "checking out ose repo"

                // defines:
                //   OPENSHIFT_DIR // by calling initialize_openshift_dir()
                ///  OSE_DIR
                //   GITHUB_URLS["ose"]
                //   GITHUB_BASE_PATHS["ose"]
                buildlib.initialize_openshift_dir()
                checkout_branch = "enterprise-${params.BUILD_VERSION}"
                if(params.BUILD_VERSION == master_ver){ checkout_branch = "master"}

                // since there's no merge and commit back, single depth is way faster
                dir( OPENSHIFT_DIR ) {
                    sh "git clone -b ${checkout_branch} --single-branch ${GITHUB_BASE}/ose.git --depth 1"
                    GITHUB_URLS["ose"] = "${GITHUB_BASE}/ose.git"
                }

                OSE_DIR = "${OPENSHIFT_DIR}/ose"
                GITHUB_BASE_PATHS["ose"] = OSE_DIR
                env.OSE_DIR = OSE_DIR
                echo "Initialized env.OSE_DIR: ${env.OSE_DIR}"
            }
            currentBuild.description = ""

            stage("rpm builds") {
                if (rpms.toUpperCase() != "NONE") {
                    currentBuild.displayName += rpms.contains(",") ? " [RPMs]" : " [${rpms} RPM]"
                    currentBuild.description = "building RPM(s): ${rpms}\n"
                    command = "--working-dir ${doozer_working} --group 'openshift-${params.BUILD_VERSION}' "
                    if (rpms) { command += "-r '${rpms}' " }
                    if (!params.SKIP_OSE) { command += "--source ose ${OSE_DIR} " }
                    command += "rpms:build --version ${version} --release ${release} "
                    buildlib.doozer command
                }
            }

            stage("puddle: ose 'building'") {
                if (rpms.toUpperCase() != "NONE") {
                    AOS_CD_JOBS_COMMIT_SHA = sh(
                        returnStdout: true,
                        script: "git rev-parse HEAD",
                    ).trim()
                    PUDDLE_CONF_BASE = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${AOS_CD_JOBS_COMMIT_SHA}/build-scripts/puddle-conf"
                    PUDDLE_CONF = "${PUDDLE_CONF_BASE}/atomic_openshift-${params.BUILD_VERSION}.conf"
                    OCP_PUDDLE = buildlib.build_puddle(
                        PUDDLE_CONF,    // The puddle configuration file to use
                        null, // openshifthosted key
                        "-b",   // do not fail if we are missing dependencies
                        "-d",   // print debug information
                        "-n",   // do not send an email for this puddle
                        "-s",   // do not create a "latest" link since this puddle is for building images
                        "--label=building"   // create a symlink named "building" for the puddle
                    )
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
                currentBuild.description += "building image(s): ${include_exclude ?: 'all'}"
                if (params.IMAGE_MODE == "nothing") { return }

                command = "--working-dir ${doozer_working} --group 'openshift-${params.BUILD_VERSION}' "
                if (!params.SKIP_OSE) { command += "--source ose ${OSE_DIR} " }
                command += "--latest-parent-version ${include_exclude} "
                command += "images:${params.IMAGE_MODE} --version ${version} --release ${release} "
                command += "--repo-type ${repo_type} "
                command += "--message 'Updating Dockerfile version and release ${version}-${release}' --push "
                buildlib.doozer command
            }

            stage("build images") {
                if (!any_images_to_build) { return }
                command = "--working-dir ${doozer_working} --group 'openshift-${params.BUILD_VERSION}' "
                command += "${include_exclude} images:build --push-to-defaults --repo-type ${repo_type} "
                buildlib.doozer command
            }

            commonlib.email(
                to: "${params.MAIL_LIST_SUCCESS}",
                from: "aos-team-art@redhat.com",
                subject: "Successful custom OCP build: ${currentBuild.displayName}",
                body: "Jenkins job: ${env.BUILD_URL}\n${currentBuild.description}");
        }
    } catch (err) {
        currentBuild.description = "failed with error: ${err}\n${currentBuild.description}"
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Error building custom OCP: ${currentBuild.displayName}",
            body: """Encountered an error while running OCP pipeline:

${currentBuild.description}

Jenkins job: ${env.BUILD_URL}
Job console: ${env.BUILD_URL}/console
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
