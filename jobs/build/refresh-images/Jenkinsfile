#!/usr/bin/env groovy

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

def mail_success(commonlib) {
    commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            from: "aos-cicd@redhat.com",
            replyTo: 'aos-team-art@redhat.com',
            subject: "Images have been refreshed: ${OSE_MAJOR}.${OSE_MINOR}",
            body: """\
Jenkins job: ${env.BUILD_URL}
${OSE_MAJOR}.${OSE_MINOR}
""");
}

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '720'
                )
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'GITHUB_BASE',
                        description: 'Github base for repos',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: "git@github.com:openshift\ngit@github.com:jupierce\ngit@github.com:jupierce-aos-cd-bot\ngit@github.com:adammhaile-aos-cd-bot",
                        defaultValue: 'git@github.com:openshift'
                    ],
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    [
                        name: 'VERSION_OVERRIDE',
                        description: 'Optional version to use. (i.e. v3.6.17). Defaults to "auto"',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'auto'
                    ],

                    [
                        name: 'RELEASE_OVERRIDE',
                        description: 'Optional release to use. Must be > 1 (i.e. 2)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ''
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-team-art@redhat.com'
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-team-art@redhat.com'
                    ],
                    commonlib.mockParam(),
                    // TODO reenable when the mirrors have the necessary puddles
                    [
                        name: 'BUILD_AMI',
                        description: 'Build golden image after building images?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'BUILD_ONLY',
                        description: 'Only rebuild specific images. Comma or space separated list. (e.g. cri-o,aos3-installation)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'BUILD_EXCLUSIONS',
                        description: 'Exclude these images from builds. Comma or space separated list. (e.g. cri-o,aos3-installation)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY_ID',
                        description: 'Advisory Number to attach new images to',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ''
                    ]
                ]
            ]
        ]
    )

    buildlib.initialize()

    OSE_MAJOR = BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    OSE_MINOR = BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y

    // clean up string delimiting
    BUILD_ONLY = commonlib.cleanCommaList(BUILD_ONLY)
    BUILD_EXCLUSIONS = commonlib.cleanCommaList(BUILD_EXCLUSIONS)

    echo "${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${params.MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${params.MAIL_LIST_FAILURE}]"

    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(DOOZER_WORKING)

    stage('Refresh Images') {

        // default to using the atomic-openshift package version
        // unless the caller provides a version and release
        if (VERSION_OVERRIDE == "auto") {
            doozer_update_docker_args = "--version auto --repo-type signed"
        } else {
            if (!VERSION_OVERRIDE.startsWith("v")) {
                VERSION_OVERRIDE = "v${VERSION_OVERRIDE}"
            }
            doozer_update_docker_args = "--version ${VERSION_OVERRIDE}"
        }

        // Get the OCP version from the current build
        // query-rpm-version returns "version: v3.10.0" for example
        def detected_version = buildlib.doozer("""
--working-dir ${DOOZER_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
--quiet
images:query-rpm-version
--repo-type signed
""", [capture: true]).split(' ').last()

        input(
                message: """\
Remember to rebuild signed puddles before proceeding.
You have specified version: ${VERSION_OVERRIDE}
doozer has detected the signed puddle contains: ${detected_version}
Proceed?
""")

        try {
            try {
                // Clean up old images so that we don't run out of device mapper space
                sh "docker rmi --force \$(docker images  | grep v${OSE_MAJOR}.${OSE_MINOR} | awk '{print \$3}')"
            } catch (cce) {
                echo "Error cleaning up old images: ${cce}"
            }

            sshagent(['openshift-bot']) {

                if (RELEASE_OVERRIDE != "") {
                    doozer_update_docker_args = "${doozer_update_docker_args} --release ${RELEASE_OVERRIDE}"
                }

                buildlib.kinit() // Sets up credentials for dist-git access

                /**
                 * Determine if something other than the whole list should be built.
                 * Note that --ignore-missing-base causes the rebase not to update a member image
                 * it is based on if that member is not in the build. Thus the build will rely on
                 * the member that was already in the Dockerfile, which was presumably already built.
                 * Specifying the same image in both causes an error, so don't do that.
                 */
                include = ""
                exclude = ""
                if (BUILD_ONLY != "") {
                    include = "-i ${BUILD_ONLY} --ignore-missing-base"
                }
                if (BUILD_EXCLUSIONS != "") {
                    exclude = "-x ${BUILD_EXCLUSIONS} --ignore-missing-base"
                }

                /**
                 * By default, do not specify a version or release for doozer. This will preserve the version label and remove
                 * the release label. OSBS now chooses a viable release label to prevent conflicting with pre-existing
                 * builds. Let's use that fact to our advantage.
                 */
                buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
${include} ${exclude}
images:update-dockerfile
  ${doozer_update_docker_args}
  --message 'Updating for image refresh'
  --push
  """

//
// start retry region
//
                BUILD_CONTINUED = false
                build_include = include
                build_exclude = exclude
                waitUntil {
                    try {

                        buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
${build_include} ${build_exclude}
images:build
--push-to-defaults --repo-type signed
"""
                        return true  // finish waitUntil
                    } catch (err) {
                        def record_log = buildlib.parse_record_log(DOOZER_WORKING)
                        def failed_map = buildlib.get_failed_builds(record_log, true)
                        if (failed_map) {
                            def r = buildlib.determine_build_failure_ratio(record_log)
                            if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
                                echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
                            } else {
                                buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
                            }
                        }

                        commonlib.email(
                            to: "${params.MAIL_LIST_FAILURE}",
                            from: "aos-cicd@redhat.com",
                            subject: "RESUMABLE Error during Refresh Images for OCP v${OSE_MAJOR}.${OSE_MINOR}",
                            body: """Encountered an error: ${err}
Input URL: ${env.BUILD_URL}input
Jenkins job: ${env.BUILD_URL}

BUILD / PUSH FAILURES:
${failed_map}
""")

                        def resp = input message: "Error during Image Build for OCP v${OSE_MAJOR}.${OSE_MINOR}",
                        parameters: [
                            [$class: 'hudson.model.ChoiceParameterDefinition',choices: "RETRY\nCONTINUE\nABORT", name: 'action', description: 'Retry (only the builds that failed). Continue (fails are OK, continue pipeline). Abort (terminate the pipeline).']
                        ]

                        switch (resp) {
                            case "RETRY":
                                echo "User chose retry. Build failures will be retried."
                                // cause waitUntil to loop again
                                build_include = "-i " + failed_map.keySet().join(",")
                                build_exclude = ""
                                return false
                            case "CONTINUE":
                                echo "User chose continue. Build failures are non-fatal."
                                // simply setting flag to keep required work out of input flow
                                BUILD_CONTINUED = true
                                return true // Terminate waitUntil
                            default: // ABORT
                                error("User chose to abort pipeline because of image build failures")
                        }

                    }

                }

                // a failed build won't push. If continued, do that now
                if (BUILD_CONTINUED) {
                    buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
${include} ${exclude}
images:push
--to-defaults --late-only"""
                }
            }

            if (params.BUILD_AMI) {
                // e.g. version_release = ['v3.9.0', '0.34.0.0']
                final version_release = buildlib.doozer([
                        "--working-dir ${DOOZER_WORKING}",
                        "--group openshift-${OSE_MAJOR}.${OSE_MINOR}",
                        '--images openshift-enterprise-docker',
                        '--quiet',
                        'images:print --short {version}-{release}',
                ].join(' '), [capture: true]).split('-')
                buildlib.build_ami(
                        OSE_MAJOR, OSE_MINOR,
                        version_release[0].substring(1), version_release[1],
                        "release-${OSE_MAJOR}.${OSE_MINOR}",
                        params.MAIL_LIST_FAILURE)
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(commonlib)


        } catch (err) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            commonlib.email(
                to: "${params.MAIL_LIST_FAILURE}",
                from: "aos-cicd@redhat.com",
                subject: "Error Refreshing Images: ${OSE_MAJOR}.${OSE_MINOR}",
                body: """Encoutered an error while running ${env.JOB_NAME}: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            commonlib.safeArchiveArtifacts([
                "doozer_working/verify_fail_log.yml",
                "doozer_working/*.log",
                "doozer_working/brew-logs/**",
                "doozer_working/*.yaml",
                "doozer_working/*.yml",
            ])
        }

    }

    stage ('Attach Images') {
        if (ADVISORY_ID != "") {
            try {
                buildlib.elliott """
 --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
 advisory:find-builds
 --kind image
 --attach ${ADVISORY_ID}
"""
            } catch ( attach_err ) {
                // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
                commonlib.email(
                    to: "${params.MAIL_LIST_FAILURE}",
                    from: "aos-cicd@redhat.com",
                    subject: "Error Attaching ${OSE_MAJOR}.${OSE_MINOR} images to ${ADVISORY_ID}","""


Jenkins job: ${env.BUILD_URL}
""");
            }
        } else {
            echo 'Skipping stage...'
        }
    }
}
