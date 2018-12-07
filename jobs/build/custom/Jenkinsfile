
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
                [
                    name: 'BUILD_VERSION',
                    description: 'OCP Version to build',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "4.0\n3.11\n3.10\n3.9\n3.8\n3.7\n3.6\n3.5\n3.4\n3.3",
                    defaultValue: '4.0'
                ],
                [
                    name: 'VERSION',
                    description: 'Version string for build (i.e. v4.0.0)',
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
                        // 'aos-art-requests@redhat.com'
                    ].join(',')
                ],
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ]
            ]
        ],
    ]
)


TARGET_NODE = "openshift-build-1"
GITHUB_BASE = "git@github.com:openshift"
SSH_KEY_ID = "openshift-bot"


REBASE_IMAGES = REBASE_IMAGES.toBoolean()
REPO_TYPE = "unsigned"
if(SIGNED.toBoolean()) { REPO_TYPE = "signed" }


node(TARGET_NODE) {
    checkout scm

    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }


    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
    }

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)

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
                buildlib.initialize_ose()

                master_spec = buildlib.read_spec_info(GITHUB_BASE_PATHS['ose'] + "/origin.spec")
                IS_SOURCE_IN_MASTER = (BUILD_VERSION == master_spec.major_minor)

                if (IS_SOURCE_IN_MASTER) {
                    OSE_SOURCE_BRANCH = "master"
                } else {
                    OSE_SOURCE_BRANCH = "enterprise-${BUILD_VERSION}"
                    // Create the non-master source branch and have it track the origin ose repo
                    sh "git checkout -b ${OSE_SOURCE_BRANCH} origin/${OSE_SOURCE_BRANCH}"
                }
            }

            stage("rpm builds") {
                if (RPMS.toUpperCase() != "NONE") {
                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${BUILD_VERSION}' "
                    command += "--source ose ${OSE_DIR} "
                    if (!RPMS?.trim()) { command += "-r '${RPMS}' " }
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
                    command += "--source ose ${OSE_DIR} "
                    if (!IMAGES?.trim()) { command += "-i '${IMAGES}' " }
                    command += "images:${TASK} --version v${VERSION} --release ${RELEASE} "
                    command += "--repo-type ${REPO_TYPE} "
                    command += "--message 'Updating Dockerfile version and release v${VERSION}-${RELEASE}' --push "
                    buildlib.doozer command
                }
            }

            BUILD_EXCLUSIONS = ""
            stage("build images") {
                if (IMAGES.toUpperCase() != "NONE") {
                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${BUILD_VERSION}' "
                    if (!IMAGES?.trim()) { command += "-i '${IMAGES}' " }
                    command += "images:build --version v${VERSION} --release ${RELEASE} "
                    command += "--push-to-defaults --repo-type unsigned "
                    try {
                        buildlib.doozer command
                    }
                    catch (err) {
                        failed_map = buildlib.get_failed_builds(DOOZER_WORKING)
                        BUILD_EXCLUSIONS = failed_map.keySet().join(",")
                    }
                }
            }

            if(BUILD_EXCLUSIONS) {
                mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-team-art@redhat.com",
                subject: "PARTIAL custom OCP build: ${VERSION}-${RELEASE}",
                body: "Some images failed during custom OCP build:\n${BUILD_EXCLUSIONS}\n\nJenkins job: ${env.BUILD_URL}");
            }
            else {
                mail(to: "${MAIL_LIST_SUCCESS}",
                from: "aos-team-art@redhat.com",
                subject: "Successful custom OCP build: ${VERSION}-${RELEASE}",
                body: "Jenkins job: ${env.BUILD_URL}");
            }
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
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: "doozer_working/*.log"
            archiveArtifacts allowEmptyArchive: true, artifacts: "doozer_working/brew-logs/**"
        } catch (aae) {
        }
    }
}