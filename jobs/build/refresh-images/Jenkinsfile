#!/usr/bin/env groovy

OCP_VERSIONS = [
        "3.11",
        "3.10",
        "3.9",
        "3.8",
        "3.7",
        "3.6",
        "3.5",
        "3.4",
        "3.3",
        "3.2",
        "3.1",
]


// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if (env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

def mail_success() {
    mail(
            to: "${MAIL_LIST_SUCCESS}",
            from: "aos-cicd@redhat.com",
            replyTo: 'aos-team-art@redhat.com',
            subject: "Images have been refreshed: ${OSE_MAJOR}.${OSE_MINOR}",
            body: """\
Jenkins job: ${env.BUILD_URL}
${OSE_MAJOR}.${OSE_MINOR}
""");
}

node('openshift-build-1') {
    checkout scm

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
                    [
                            name: 'BUILD_VERSION',
                            description: 'OSE Version',
                            $class: 'hudson.model.ChoiceParameterDefinition',
                            choices: OCP_VERSIONS.join('\n'),
                            defaultValue: '3.9'
                    ],
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
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'tbielawa@redhat.com,jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com,jodavis@redhat.com,lmeyer@redhat.com'
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'tbielawa@redhat.com,jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com,jodavis@redhat.com,lmeyer@redhat.com'
                    ],
                    [
                        name: 'MOCK',
                        description: 'Mock run to pickup new Jenkins parameters?.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    // TODO reenable when the mirrors have the necessary puddles
                    [
                        name: 'BUILD_AMI',
                        description: 'Build golden image after building images?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'BUILD_EXCLUSIONS',
                        description: 'Exclude these images from builds. Comma or space separated list. (i.e cri-o-docker,aos3-installation-docker)',
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

    OSE_MAJOR = BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    OSE_MINOR = BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y

    if (BUILD_EXCLUSIONS != "") {
        // clean up string delimiting
        BUILD_EXCLUSIONS = BUILD_EXCLUSIONS.replaceAll(',', ' ')
        BUILD_EXCLUSIONS = BUILD_EXCLUSIONS.split().join(',')
    }

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], MOCK:${MOCK}"

    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}"

    if (MOCK.toBoolean()) {
        error("Ran in mock mode")
    }

    set_workspace()

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize()

    stage("enterprise-images repo") {
        buildlib.initialize_enterprise_images_dir()
    }

    // oit_working must be in WORKSPACE in order to have artifacts archived
    OIT_WORKING = "${WORKSPACE}/oit_working"
    //Clear out previous work
    sh "rm -rf ${OIT_WORKING}"
    sh "mkdir -p ${OIT_WORKING}"

    stage('Refresh Images') {

        // default to using the atomic-openshift package version
        // unless the caller provides a version and release
        if (VERSION_OVERRIDE == "auto") {
            oit_update_docker_args = "--version auto --repo-type signed"
        } else {
            if (!VERSION_OVERRIDE.startsWith("v")) {
                error("Version overrides must start with 'v'")
            }
            oit_update_docker_args = "--version ${VERSION_OVERRIDE}"
        }

        // Get the OCP version from the current build
        // query-rpm-version returns "version: v3.10.0" for example
        def detected_version = buildlib.oit("""
--working-dir ${OIT_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
--quiet
images:query-rpm-version
--repo-type signed
""", [capture: true]).split(' ').last()

        input(
                message: """\
Remember to rebuild signed puddles before proceeding.
You have specified version: ${VERSION_OVERRIDE}
oit has detected the signed puddle contains: ${detected_version}
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
                    oit_update_docker_args = "${oit_update_docker_args} --release ${RELEASE_OVERRIDE}"
                }

                buildlib.kinit() // Sets up credentials for dist-git access

                /**
                 * By default, do not specify a version or release for oit. This will preserve the version label and remove
                 * the release label. OSBS now chooses a viable release label to prevent conflicting with pre-existing
                 * builds. Let's use that fact to our advantage.
                 */
                buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
images:update-dockerfile
  ${oit_update_docker_args}
  --message 'Updating for image refresh'
  --push
  """

//
// start retry region
//
                BUILD_CONTINUED = false
                waitUntil {
                    try {
                        exclude = ""
                        if (BUILD_EXCLUSIONS != "") {
                            exclude = "-x ${BUILD_EXCLUSIONS} --ignore-missing-base"
                        }

                        buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
${exclude}
images:build
--push-to-defaults --repo-type signed
"""
                        return true  // finish waitUntil
                    } catch (err) {
                        failed_builds = buildlib.get_failed_builds(OIT_WORKING)

                        mail(
                            to: "${MAIL_LIST_FAILURE}",
                            from: "aos-cicd@redhat.com",
                            subject: "RESUMABLE Error during Refresh Images for OCP v${OSE_MAJOR}.${OSE_MINOR}",
                            body: """Encountered an error: ${err}
Input URL: ${env.BUILD_URL}input
Jenkins job: ${env.BUILD_URL}

BUILD / PUSH FAILURES:
${failed_builds}
""")

                        def resp = input message: "Error during Image Build for OCP v${OSE_MAJOR}.${OSE_MINOR}",
                        parameters: [
                            [$class: 'hudson.model.ChoiceParameterDefinition',choices: "RETRY\nCONTINUE\nABORT", name: 'action', description: 'Retry (try the operation again). Continue (fails are OK, continue pipeline). Abort (terminate the pipeline).']
                        ]

                        switch (resp) {
                            case "RETRY":
                                // cause waitUntil to loop again
                                return false
                            case "CONTINUE":
                                echo "User chose continue. Build failures are non-fatal."
                                //will make email show PARTIAL, don't try to rebuild failures, only unbuilt
                                BUILD_EXCLUSIONS = failed_builds.keySet().join(",")
                                //simply setting flag to keep required work out of input flow
                                BUILD_CONTINUED = true
                                return true // Terminate waitUntil
                            default: // ABORT
                                error("User chose to abort pipeline because of image build failures")
                        }

                    }

                }

                // a failed build won't push. If continued, do that now
                if (BUILD_CONTINUED) {
                    buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
${exclude}
images:push
--to-defaults --late-only"""
                    // exclude is already set earlier in the main images:build flow
                }
            }

            try {
                buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
${exclude}
images:verify
--repo-type signed
"""
            } catch (vererr) {
                echo "Error verifying images: ${vererr}"
                mail(to: "${MAIL_LIST_FAILURE}",
                     from: "aos-cicd@redhat.com",
                     subject: "Error Verifying Images During Refresh: ${OSE_MAJOR}.${OSE_MINOR}",
                     body: """Encoutered an error while running ${env.JOB_NAME}: ${vererr}


Jenkins job: ${env.BUILD_URL}
""");
            }

            if (params.BUILD_AMI) {
                // e.g. version_release = ['v3.9.0', '0.34.0.0']
                final version_release = buildlib.oit([
                        "--working-dir ${OIT_WORKING}",
                        "--group openshift-${OSE_MAJOR}.${OSE_MINOR}",
                        '--images openshift-enterprise-docker',
                        '--quiet',
                        'images:print --short {version}-{release}',
                ].join(' '), [capture: true]).split('-')
                buildlib.build_ami(
                        OSE_MAJOR, OSE_MINOR,
                        version_release[0].substring(1), version_release[1],
                        "release-${OSE_MAJOR}.${OSE_MINOR}",
                        MAIL_LIST_FAILURE)
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success()


        } catch (err) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cicd@redhat.com",
                    subject: "Error Refreshing Images: ${OSE_MAJOR}.${OSE_MINOR}",
                    body: """Encoutered an error while running ${env.JOB_NAME}: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            try {
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/verify_fail_log.yml"
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/*.log"
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/brew-logs/**"
            } catch (aae) {
            }
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
                mail(to: "${MAIL_LIST_FAILURE}",
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
