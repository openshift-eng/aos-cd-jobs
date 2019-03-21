#!/usr/bin/env groovy


def get_mirror_url(build_mode, version) {
    if (build_mode == "online:int") {
        return "https://mirror.openshift.com/enterprise/online-int"
    }
    return "https://mirror.openshift.com/enterprise/enterprise-${version}"
}

def mail_success(version, mirrorURL, record_log, commonlib) {

    def target = "(Release Candidate)"

    if (BUILD_MODE == "online:int") {
        target = "(Integration Testing)"
    }

    def inject_notes = ""
    if (params.SPECIAL_NOTES.trim() != "") {
        inject_notes = "\n***Special notes associated with this build****\n${params.SPECIAL_NOTES.trim()}\n***********************************************\n"
    }

    def timing_report = get_build_timing_report(record_log)
    def image_list = get_image_build_report(record_log)
    currentBuild.description = timing_report
    currentBuild.result = "SUCCESS"
    PARTIAL = " "
    mail_list = params.MAIL_LIST_SUCCESS
    exclude_subject = ""
    if (BUILD_EXCLUSIONS != "" || BUILD_FAILURES != null) {
        PARTIAL = " PARTIAL "
        currentBuild.displayName += " (partial)"
        if (BUILD_FAILURES != null) {
            mail_list = params.MAIL_LIST_FAILURE
            exclude_subject += " [failed images: ${BUILD_FAILURES}]"
        }
        if (BUILD_EXCLUSIONS != "") {
            exclude_subject += " [excluded images: ${BUILD_EXCLUSIONS}]"
        }
    }

    image_details = """${timing_report}
Images:
  - Images have been pushed to registry.reg-aws.openshift.com:443     (Get pull access [1])
    [1] https://github.com/openshift/ops-sop/blob/master/services/opsregistry.asciidoc#using-the-registry-manually-using-rh-sso-user
${image_list}
"""


    if (!params.BUILD_CONTAINER_IMAGES) {
        PARTIAL = " RPM ONLY "
        image_details = ""
        // Just inform key folks about RPM only build; this is just prepping for an advisory.
        mail_list = params.MAIL_LIST_FAILURE
    }

    commonlib.email(
        to: "${mail_list}",
        from: "aos-cicd@redhat.com",
        subject: "[aos-cicd] New${PARTIAL}build for OpenShift ${target}: ${version}${exclude_subject}",
        body: """\
OpenShift Version: v${version}
${inject_notes}
RPMs:
    Puddle (internal): http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${params.BUILD_VERSION}/${OCP_PUDDLE}
    Exernal Mirror: ${mirrorURL}/${OCP_PUDDLE}
${image_details}

Brew:
  - Openshift: ${OSE_BREW_URL}

Jenkins job: ${env.BUILD_URL}

Are your Atomic OpenShift changes in this build? Check here:
https://github.com/openshift/ose/commits/v${NEW_VERSION}-${NEW_RELEASE}/

""");

    try {
        if (BUILD_EXCLUSIONS == "" && params.BUILD_CONTAINER_IMAGES) {
            timeout(3) {
                sendCIMessage(
                    messageContent: "New build for OpenShift ${target}: ${version}",
                    messageProperties:
                        """build_mode=${BUILD_MODE}
                        puddle_url=${mirrorURL}/${OCP_PUDDLE}
                        image_registry_root=registry.reg-aws.openshift.com:443
                        brew_task_url_openshift=${OSE_BREW_URL}
                        product=OpenShift Container Platform
                        """,
                    messageType: 'ProductBuildDone',
                    overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                    providerName: 'Red Hat UMB'
                )
            }
        }
    } catch (mex) {
        echo "Error while sending CI message: ${mex}"
    }
}

// extract timing information from the record_log and write a report string
// the timing record log entry has this form:
// image_build_metrics|elapsed_total_minutes={d}|task_count={d}|elapsed_wait_minutes={d}|
def get_build_timing_report(record_log) {
    metrics = record_log['image_build_metrics']

    if (metrics == null || metrics.size() == 0) {
        return ""
    }

    return """
Images built: ${metrics[0]['task_count']}
Elapsed image build time: ${metrics[0]['elapsed_total_minutes']} minutes
Time spent waiting for OSBS capacity: ${metrics[0]['elapsed_wait_minutes']} minutes
"""
}

// get the list of images built
def get_image_build_report(record_log) {
    builds = record_log['build']

    if ( builds == null ) {
        return ""
    }

    Set image_set = []
    for (i = 0; i < builds.size(); i++) {
        bld = builds[i]
        if (bld['status'] == "0" && bld['push_status'] == "0") {
            image_spec_string =
                "${bld['image']}:${bld['version']}-${bld['release']}"
            image_set << image_spec_string
        }
    }

    return "\nImages included in build:\n    " +
        image_set.toSorted().join("\n    ")
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
                    numToKeepStr: '1000')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    [
                        name: 'NEW_VERSION',
                        description: '(Optional) version for build instead of most recent\nor "+" to bump most recent version',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'BUILD_CONTAINER_IMAGES',
                        description: 'Build container images? Otherwise just RPMs',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: true
                    ],
                    [
                        name: 'BUILD_EXCLUSIONS',
                        description: 'Exclude these images from builds. Comma or space separated list. (i.e cri-o-docker,aos3-installation-docker)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    commonlib.mockParam(),
                    [
                        name: 'DRY_RUN',
                        description: 'Take no action, just echo what the build would have done.',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'BUILD_MODE',
                        description: '''
Determines where the compose is mirrored:
    pre-release               origin/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/
    online:int                origin/master -> online-int yum repo
    ''',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "pre-release",
                            "online:int"
                        ].join("\n"),
                        defaultValue: "pre-release"
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-team-art@redhat.com',
                        ].join(',')
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-team-art@redhat.com'
                        ].join(',')
                    ],
                    [
                        name: 'SPECIAL_NOTES',
                        description: 'Include special notes in the build email?',
                        $class: 'hudson.model.TextParameterDefinition',
                        defaultValue: ""
                    ],
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    GITHUB_BASE = "git@github.com:openshift"  // buildlib uses this :eyeroll:
    commonlib.checkMock()

    BUILD_VERSION_MAJOR = params.BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    BUILD_VERSION_MINOR = params.BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y

    BUILD_EXCLUSIONS = commonlib.cleanCommaList(params.BUILD_EXCLUSIONS)
    BUILD_FAILURES = null

    aosCdJobsCommitSha = sh(
        returnStdout: true,
        script: "git rev-parse HEAD",
    ).trim()

    puddleConfBase = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${aosCdJobsCommitSha}/build-scripts/puddle-conf"
    puddleConf = "${puddleConfBase}/atomic_openshift-${params.BUILD_VERSION}.conf"

    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}.??"
    echo "Initializing build: ${currentBuild.displayName}"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${env.WORKSPACE}/doozer_working"
    // get a fresh one, but delay removing the old one
    sh "mkdir -p ${DOOZER_WORKING}; mv ${DOOZER_WORKING} ${DOOZER_WORKING}.${currentBuild.number}; mkdir -p ${DOOZER_WORKING}"

    try {
        stage("version") {
            // inputs:
            //  BUILD_VERSION

            // defines:
            //  NEW_VERSION
            //  NEW_RELEASE
            //  NEW_DOCKERFILE_RELEASE
            //
            //  sets currentBuild.displayName

            def prevBuild = sh(
                returnStdout: true,
                script: "brew latest-build --quiet rhaos-${params.BUILD_VERSION}-rhel-7-candidate openshift | awk '{print \$1}'"
            ).trim()

            def extractBuildVersion = { build ->
                // closure also keeps regex away from pipeline steps (error|echo)
                def match = build =~ /(?x) ^openshift- (  \d+  ( \. \d+ )+  )-/
                return match ? match[0][1] : "" // first group in the regex
            }

            NEW_VERSION = "${params.BUILD_VERSION}.0"  // default
            if(params.NEW_VERSION.trim() == "+") {
                // increment previous build version
                NEW_VERSION = extractBuildVersion(prevBuild)
                if (!NEW_VERSION) {
                    error("Could not determine version from last build '${prevBuild}'")
                }
                def segments = NEW_VERSION.split("\\.").collect { it.toInteger() }
                segments[-1]++
                NEW_VERSION = segments.join(".")
                echo("Using version ${NEW_VERSION} incremented from latest openshift package ${prevBuild}")
            } else if(params.NEW_VERSION) {
                // explicit version given
                NEW_VERSION = commonlib.standardVersion(params.NEW_VERSION, false)
                echo("Using NEW_VERSION parameter for version: ${NEW_VERSION}")
            } else if (prevBuild) {
                // use version from previous build
                NEW_VERSION = extractBuildVersion(prevBuild)
                if (!NEW_VERSION) {
                    error("Could not determine version from last build '${prevBuild}'")
                }
                echo("Using version ${NEW_VERSION} from latest openshift package ${prevBuild}")
            }

            if (! NEW_VERSION.startsWith("${params.BUILD_VERSION}.")) {
                // The version we came up with somehow doesn't match what we expect to build; abort
                error("Determined a version, '${NEW_VERSION}', that does not begin with ${params.BUILD_VERSION}!")
            }

            NEW_RELEASE = new Date().format("yyyyMMddHHmm")
            NEW_DOCKERFILE_RELEASE = NEW_RELEASE

            currentBuild.displayName = "#${currentBuild.number} - ${NEW_VERSION}-${NEW_RELEASE}"
            if (!params.BUILD_CONTAINER_IMAGES) { currentBuild.displayName += " (RPM ONLY)" }
            if (params.DRY_RUN) { currentBuild.displayName += " (DRY RUN)" }
        }

        sshagent(["openshift-bot"]) {
            // To work on private repos, buildlib operations must run with the permissions of openshift-bot

            stage("doozer build rpms") {
                def cmd =
"""
--working-dir ${DOOZER_WORKING} --group 'openshift-${params.BUILD_VERSION}'
rpms:build --version v${NEW_VERSION}
--release ${NEW_RELEASE}
"""

                parallel "remove previous workspace(s)": { ->
                    // this can take a while, given NFS. do while building RPMs.
                    sh script: "rm -rf ${DOOZER_WORKING}.*", returnStatus: true
                },
                "build RPMs": { ->
                    params.DRY_RUN ? echo("doozer ${cmd}") : buildlib.doozer(cmd)
                }


            }

            stage("puddle: ose 'building'") {
                if(params.DRY_RUN) {
                    echo "Build puddle with conf ${puddleConf}"
                    return
                }
                OCP_PUDDLE = buildlib.build_puddle(
                    puddleConf,    // The puddle configuration file to use
                    null,   // signing key
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n",   // do not send an email for this puddle
                    "-s",   // do not create a "latest" link since this puddle is for building images
                    "--label=building"   // create a symlink named "building" for the puddle
                )
            }

            stage("update dist-git") {
                if (!params.BUILD_CONTAINER_IMAGES) {
                    return
                }
                def cmd =
"""
--working-dir ${DOOZER_WORKING} --group 'openshift-${params.BUILD_VERSION}'
images:rebase --version v${NEW_VERSION}
--release ${NEW_DOCKERFILE_RELEASE}
--message 'Updating Dockerfile version and release v${NEW_VERSION}-${NEW_DOCKERFILE_RELEASE}' --push
"""
                if(params.DRY_RUN) {
                    echo "doozer ${cmd}"
                    return
                }
                buildlib.doozer cmd
                buildlib.notify_dockerfile_reconciliations(DOOZER_WORKING, params.BUILD_VERSION)
            }

            stage("build images") {
                if (params.BUILD_CONTAINER_IMAGES) {
                    try {
                        exclude = ""
                        if (BUILD_EXCLUSIONS != "") {
                            exclude = "-x ${BUILD_EXCLUSIONS} --ignore-missing-base"
                        }
                        def cmd =
"""
--working-dir ${DOOZER_WORKING} --group openshift-${params.BUILD_VERSION}
${exclude}
images:build
--push-to-defaults --repo-type unsigned
"""
                        if(params.DRY_RUN) {
                            echo "doozer ${cmd}"
                            return
                        }
                        buildlib.doozer cmd
                    }
                    catch (err) {
                        record_log = buildlib.parse_record_log(DOOZER_WORKING)
                        def failed_map = buildlib.get_failed_builds(record_log, true)
                        if (!failed_map) { throw err }  // failed so badly we don't know what failed; assume all

                        BUILD_FAILURES = failed_map.keySet().join(",")  // will make email show PARTIAL
                        currentBuild.result = "UNSTABLE"
                        currentBuild.description = "Failed images: ${BUILD_FAILURES}"

                        def r = buildlib.determine_build_failure_ratio(record_log)
                        if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
                            echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
                        } else {
                            buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
                        }
                    }
                }
            }

            stage("mirror RPMs") {
                if(params.DRY_RUN) {
                    return
                }

                NEW_FULL_VERSION = "${NEW_VERSION}-${NEW_RELEASE}"

                SYMLINK_NAME = "latest"
                if (!params.BUILD_CONTAINER_IMAGES) {
                    SYMLINK_NAME = "no-image-latest"
                }

                // Push the building puddle out to the correct directory on the mirrors (e.g. online-int, online-stg, or enterprise-X.Y)
                buildlib.invoke_on_rcm_guest("push-to-mirrors.sh", SYMLINK_NAME, NEW_FULL_VERSION, BUILD_MODE)

                // push-to-mirrors.sh sets up a different puddle name on rcm-guest and the mirrors
                OCP_PUDDLE = "v${NEW_FULL_VERSION}_${OCP_PUDDLE}"
                final mirror_url = get_mirror_url(BUILD_MODE, params.BUILD_VERSION)

                buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", params.BUILD_VERSION, NEW_FULL_VERSION, "openshift")

                echo "Finished building OCP ${NEW_FULL_VERSION}"
                mail_success(NEW_FULL_VERSION, mirror_url, record_log, commonlib)

            }

            stage('sync images') {
                if (params.DRY_RUN || !params.BUILD_CONTAINER_IMAGES) {
                    return
                }
                buildlib.sync_images(
                    BUILD_VERSION_MAJOR,
                    BUILD_VERSION_MINOR,
                    "aos-team-art@redhat.com",
                    currentBuild.number
                )
            }
        }
    } catch (err) {

        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-cicd@redhat.com",
            subject: "Error building OSE: ${params.BUILD_VERSION}",
            body: """Encountered an error while running OCP pipeline: ${err}

Jenkins job: ${env.BUILD_URL}
        """);
        currentBuild.description = "Error while running OCP pipeline:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    } finally {
        commonlib.safeArchiveArtifacts([
            "doozer_working/*.log",
            "doozer_working/brew-logs/**",
            "doozer_working/*.yaml",
            "doozer_working/*.yml",
        ])
    }
}
