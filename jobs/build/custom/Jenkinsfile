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
                    commonlib.oseVersionParam('BUILD_VERSION'),
                    [
                        name: 'VERSION',
                        description: 'Version string for build without leading "v" (i.e. 4.0.0)',
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
                        name: 'REBASE_IMAGES',
                        description: 'Run images:rebase? Otherwise use images:update-dockerfile',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: true
                    ],
                    [
                        name: 'SIGNED',
                        description: 'Build against signed RPMs?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
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

    MASTER_VER = commonlib.ocpDefaultVersion
    GITHUB_BASE = "git@github.com:openshift"
    SSH_KEY_ID = "openshift-bot"

    REBASE_IMAGES = REBASE_IMAGES.toBoolean()
    REPO_TYPE = SIGNED.toBoolean() ? "signed" : "unsigned"
    IMAGES = commonlib.cleanCommaList(IMAGES)

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    //Clear out previous work
    sh "rm -rf ${DOOZER_WORKING}"
    sh "mkdir -p ${DOOZER_WORKING}"

    try {
        sshagent([SSH_KEY_ID]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot

            // Some images require OSE as a source.
            // Instead of trying to figure out which do, always clone
            stage("ose repo") {
                // defines:
                //   OPENSHIFT_DIR // by calling initialize_openshift_dir()
                ///  OSE_DIR
                //   GITHUB_URLS["ose"]
                //   GITHUB_BASE_PATHS["ose"]
                buildlib.initialize_openshift_dir()
                CHECKOUT_BRANCH = "enterprise-${BUILD_VERSION}"
                if(BUILD_VERSION == MASTER_VER){ CHECKOUT_BRANCH = "master"}

                // since there's no merge and commit back, single depth is way faster
                dir( OPENSHIFT_DIR ) {
                    sh "git clone -b ${CHECKOUT_BRANCH} --single-branch ${GITHUB_BASE}/ose.git --depth 1"
                    GITHUB_URLS["ose"] = "${GITHUB_BASE}/ose.git"
                }

                OSE_DIR = "${OPENSHIFT_DIR}/ose"
                GITHUB_BASE_PATHS["ose"] = OSE_DIR
                env.OSE_DIR = OSE_DIR
                echo "Initialized env.OSE_DIR: ${env.OSE_DIR}"
            }

            stage("rpm builds") {
                if (RPMS.toUpperCase() != "NONE") {
                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${BUILD_VERSION}' "
                    command += "--source ose ${OSE_DIR} "
                    if (RPMS?.trim()) { command += "-r '${RPMS}' " }
                    command += "rpms:build --version v${VERSION} --release ${RELEASE} "
                    buildlib.doozer command
                }
            }

            stage("puddle: ose 'building'") {
                if (RPMS.toUpperCase() != "NONE") {
                    AOS_CD_JOBS_COMMIT_SHA = sh(
                        returnStdout: true,
                        script: "git rev-parse HEAD",
                    ).trim()
                    PUDDLE_CONF_BASE = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${AOS_CD_JOBS_COMMIT_SHA}/build-scripts/puddle-conf"
                    PUDDLE_CONF = "${PUDDLE_CONF_BASE}/atomic_openshift-${BUILD_VERSION}.conf"
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

            stage("update dist-git") {
                if (IMAGES.toUpperCase() != "NONE") {
                    TASK = "update-dockerfile"
                    if(REBASE_IMAGES) { TASK = "rebase" }

                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${BUILD_VERSION}' "
                    command += "--source ose ${OSE_DIR} --latest-parent-version "
                    if (IMAGES?.trim()) { command += "-i '${IMAGES}' " }
                    command += "images:${TASK} --version v${VERSION} --release ${RELEASE} "
                    command += "--repo-type ${REPO_TYPE} "
                    command += "--message 'Updating Dockerfile version and release v${VERSION}-${RELEASE}' --push "
                    buildlib.doozer command
                }
            }

            stage("build images") {
                if (IMAGES.toUpperCase() != "NONE") {
                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${BUILD_VERSION}' "
                    if (IMAGES?.trim()) { command += "-i '${IMAGES}' " }
                    command += "images:build --push-to-defaults --repo-type ${REPO_TYPE} "
                    buildlib.doozer command
                }
            }

            mail(to: "${MAIL_LIST_SUCCESS}",
                from: "aos-team-art@redhat.com",
                subject: "Successful custom OCP build: ${VERSION}-${RELEASE}",
                body: "Jenkins job: ${env.BUILD_URL}");
        }
    } catch (err) {
        mail(to: "${MAIL_LIST_FAILURE}",
             from: "aos-team-art@redhat.com",
             subject: "Error building custom OCP: v${VERSION}-${RELEASE}",
             body: """Encountered an error while running OCP pipeline: ${err}

    Jenkins job: ${env.BUILD_URL}
    """);

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
