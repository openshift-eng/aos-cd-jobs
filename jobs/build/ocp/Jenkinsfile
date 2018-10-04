#!/usr/bin/env groovy

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
                    name: 'TARGET_NODE',
                    description: 'Jenkins agent node',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'openshift-build-1'
                ],
                [
                    name: 'GITHUB_BASE',
                    description: 'Github base for repos',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "git@github.com:openshift",
                        "git@github.com:jupierce",
                        "git@github.com:jupierce-aos-cd-bot",
                        "git@github.com:adammhaile-aos-cd-bot",
                        "git@github.com:markllama"
                    ].join("\n"),
                    defaultValue: 'git@github.com:openshift'
                ],
                [
                    name: 'SSH_KEY_ID',
                    description: 'SSH credential id to use',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "openshift-bot",
                        "aos-cd-test",
                        "jupierce-aos-cd-bot",
                        "adammhaile-aos-cd-bot",
                        "markllama-aos-cd-bot"
                    ].join("\n"),
                    defaultValue: 'aos-cd-test'
                ],
                [
                    name: 'BUILD_VERSION',
                    description: 'OCP Version to build',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "4.0\n3.11\n3.10\n3.9\n3.8\n3.7\n3.6\n3.5\n3.4\n3.3",
                    defaultValue: '4.0'
                ],
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
                    name: 'BUILD_MODE',
                    description: '''
auto                      BUILD_VERSION and ocp repo contents determine the mode<br>
release                   {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
pre-release               {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
online:stg                {origin,origin-web-console,openshift-ansible}/stage -> online-stg yum repo<br>
''',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "auto",
                        "release",
                        "pre-release",
                        "online:int",
                        "online:stg"
                    ].join("\n"),
                    defaultValue: "auto"
                ],
                [
                    name: 'ODCS',
                    description: 'Run in ODCS Mode?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'SIGN',
                    description: 'Sign RPMs with openshifthosted?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'TEST',
                    description: 'Run as much code as possible without pushing / building?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'SPECIAL_NOTES',
                    description: 'Include special notes in the build email?',
                    $class: 'hudson.model.TextParameterDefinition',
                    defaultValue: ""
                ],
                [
                    name: 'BUILD_EXCLUSIONS',
                    description: 'Exclude these images from builds. Comma or space separated list. (i.e cri-o-docker,aos3-installation-docker)',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ""
                ],
                [
                    name: 'BUILD_CONTAINER_IMAGES',
                    description: 'Build container images?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: true
                ],
                [
                    name: 'BUILD_AMI',
                    description: 'Build golden image after building images?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: true
                ],
            ]
        ],
        disableConcurrentBuilds()
    ]
)

IS_TEST_MODE = TEST.toBoolean()
BUILD_VERSION_MAJOR = BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
BUILD_VERSION_MINOR = BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y
SIGN_RPMS = SIGN.toBoolean()
BUILD_CONTAINER_IMAGES = BUILD_CONTAINER_IMAGES.toBoolean()
ODCS_MODE = ODCS.toBoolean()
ODCS_FLAG = ""
ODCS_OPT = ""
if (ODCS_MODE) {
    ODCS_FLAG = "--odcs-mode"
    ODCS_OPT = "--odcs unsigned"
}

if (BUILD_EXCLUSIONS != "") {
    // clean up string delimiting
    BUILD_EXCLUSIONS = BUILD_EXCLUSIONS.replaceAll(',', ' ')
    BUILD_EXCLUSIONS = BUILD_EXCLUSIONS.split().join(',')
}

def get_mirror_url(build_mode, version) {
    if (build_mode == "online:int") {
        return "https://mirror.openshift.com/enterprise/online-int"
    }
    if (build_mode == "online:stg") {
        return "https://mirror.openshift.com/enterprise/online-stg"
    }
    return "https://mirror.openshift.com/enterprise/enterprise-${version}"
}

def get_changelog(rpm_name, record_log) {
    //
    // INPUTS:
    //   rpm_name - the name of an RPM build previously
    //   record_log - an array of build records with | separated fields

    rpm_builds = record_log['build_rpm']
    if (rpm_builds == null || rpm_builds.size() == 0) {
        return ""
    }

    // filter for the desired RPM using name
    build_record_index = rpm_builds.findIndexOf {
        it['rpm'] == rpm_name
    }
    if (build_record_index == -1) {
        return ""
    }
    build_record = rpm_builds[build_record_index]

    // then get the task_id and task_url out of it
    // task_id = build_record['task_id']
    task_url = build_record['task_url']

    // get the build ID from the web page
    // there must be an API way to do this MAL 20180622
    try {
        build_id = sh(
            returnStdout: true,
            script: [
                "curl --silent --insecure ${task_url}",
                "sed -n -e 's/.*buildID=\\([0-9]*\\).*/\\1/p'"
            ].join(" | ")
        ).trim()
    } catch (err) {
        error("failed to retrieve task page from brew: ${task_url}")
    }

    // buildinfo can return the changelog.  Return just the text after
    // the Changelog: line
    try {
        changelog = sh(
            returnStdout: true,
            script: [
                "brew buildinfo ${build_id} --changelog",
                "sed -n '/Changelog/,\$p'"
            ].join(' | ')
        ).trim()
    } catch (err) {
        error "failed to get build info and changelog for build ${build_id}"
    }

    return changelog
}

def mail_success(version, mirrorURL, record_log, oa_changelog) {

    def target = "(Release Candidate)"

    if (BUILD_MODE == "online:int") {
        target = "(Integration Testing)"
    }

    if (BUILD_MODE == "online:stg") {
        target = "(Stage Testing)"
    }

    def inject_notes = ""
    if (SPECIAL_NOTES.trim() != "") {
        inject_notes = "\n***Special notes associated with this build****\n${SPECIAL_NOTES.trim()}\n***********************************************\n"
    }

    def timing_report = get_build_timing_report(record_log)
    def image_list = get_image_build_report(record_log)

    PARTIAL = " "
    exclude_subject = ""
    if (BUILD_EXCLUSIONS != "") {
        PARTIAL = " PARTIAL "
        exclude_subject = " [excluded images: ${BUILD_EXCLUSIONS}]"
    }

    image_details = """${timing_report}
Images:
  - Images have been pushed to registry.reg-aws.openshift.com:443     (Get pull access [1])
    [1] https://github.com/openshift/ops-sop/blob/master/services/opsregistry.asciidoc#using-the-registry-manually-using-rh-sso-user
${image_list}
"""

    mail_list = MAIL_LIST_SUCCESS
    if (!BUILD_CONTAINER_IMAGES) {
        PARTIAL = " RPM ONLY "
        image_details = ""
        // Just inform key folks about RPM only build; this is just prepping for an advisory.
        mail_list = MAIL_LIST_FAILURE
    }

    mail(
        to: "${mail_list}",
        from: "aos-cicd@redhat.com",
        subject: "[aos-cicd] New${PARTIAL}build for OpenShift ${target}: ${version}${exclude_subject}",
        body: """\
OpenShift Version: v${version}
${inject_notes}
RPMs:
    Puddle (internal): http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${BUILD_VERSION}/${OCP_PUDDLE}
    Exernal Mirror: ${mirrorURL}/${OCP_PUDDLE}
${image_details}

Brew:
  - Openshift: ${OSE_BREW_URL}
  - OpenShift Ansible: ${OA_BREW_URL}

Jenkins job: ${env.BUILD_URL}

Are your Atomic OpenShift changes in this build? Check here:
https://github.com/openshift/ose/commits/v${NEW_VERSION}-${NEW_RELEASE}/

===Atomic OpenShift changelog snippet===
${OSE_CHANGELOG}


Are your OpenShift Ansible changes in this build? Check here:
https://github.com/openshift/openshift-ansible/commits/openshift-ansible-${NEW_VERSION}-${NEW_RELEASE}/

===OpenShift Ansible changelog snippet===
${oa_changelog}
""");

    try {
        if (BUILD_EXCLUSIONS == "" && BUILD_CONTAINER_IMAGES) {
            timeout(3) {
                sendCIMessage(
                    messageContent: "New build for OpenShift ${target}: ${version}",
                    messageProperties:
                        """build_mode=${BUILD_MODE}
                        puddle_url=${mirrorURL}/${OCP_PUDDLE}
                        image_registry_root=registry.reg-aws.openshift.com:443
                        brew_task_url_openshift=${OSE_BREW_URL}
                        brew_task_url_openshift_ANSIBLE=${OA_BREW_URL}
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

// Search the RPM build logs for the named package
// extract the path to the spec file and return the changelog section.
def get_rpm_specfile_path(record_log, package_name) {
    rpms = record_log['build_rpm']
    if (rpms == null) {
        return null
    }

    // find the named package and the spec file path
    specfile_path = ""
    for (i = 0 ; i < rpms.size(); i++) {
        if (rpms[i]['distgit_key'] == package_name) {
            specfile_path = rpms[i]['specfile']
            break
        }
    }

    return specfile_path
}

// Will be used to track which atomic-openshift build was tagged before we ran.
PREV_BUILD = null

node(TARGET_NODE) {

    checkout scm
    AOS_CD_JOBS_COMMIT_SHA = sh(
        returnStdout: true,
        script: "git rev-parse HEAD",
    ).trim()

    try {
        // Clean up old images so that we don't run out of device mapper space
        sh "docker rmi --force \$(docker images  | grep v${BUILD_VERSION} | awk '{print \$3}')"
    } catch (cce) {
        echo "Error cleaning up old images: ${cce}"
    }

    PUDDLE_CONF_BASE = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${AOS_CD_JOBS_COMMIT_SHA}/build-scripts/puddle-conf"
    PUDDLE_CONF = "${PUDDLE_CONF_BASE}/atomic_openshift-${BUILD_VERSION}.conf"
    PUDDLE_SIGN_KEYS = SIGN_RPMS ? "b906ba72" : null

    def commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(IS_TEST_MODE)
    echo "Initializing build: #${currentBuild.number} - ${BUILD_VERSION}.?? (${BUILD_MODE})"

    // oit_working must be in WORKSPACE in order to have artifacts archived
    OIT_WORKING = "${WORKSPACE}/oit_working"
    //Clear out previous work
    sh "rm -rf ${OIT_WORKING}"
    sh "mkdir -p ${OIT_WORKING}"

    try {
        sshagent([SSH_KEY_ID]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot

            PREV_BUILD = sh(
                returnStdout: true,
                script: "brew latest-build --quiet rhaos-${BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'"
            ).trim()

            stage("ose repo") {
                // defines:
                //   OPENSHIFT_DIR // by calling initialize_openshift_dir()
                ///  OSE_DIR
                //   GITHUB_URLS["ose"]
                //   GITHUB_BASE_PATHS["ose"]
                buildlib.initialize_ose()
            }

            stage("set build mode") {
                master_spec = buildlib.read_spec_info(GITHUB_BASE_PATHS['ose'] + "/origin.spec")

                // If the target version resides in ose#master
                IS_SOURCE_IN_MASTER = (BUILD_VERSION == master_spec.major_minor)

                if (BUILD_MODE == "auto") {
                    echo "AUTO-MODE: determine mode from version and repo: BUILD_VERSION: ${BUILD_VERSION}, master_version: ${master_spec.major_minor}"
                    // INPUTS:
                    //   BUILD_MODE
                    //   BUILD_VERSION
                    //   GITHUB_URLS["ose"]
                    releases = buildlib.get_releases(GITHUB_URLS['ose'])
                    echo "AUTO-MODE: release repo: ${GITHUB_URLS['ose']}"
                    echo "AUTO-MODE: releases: ${releases}"
                    BUILD_MODE = buildlib.auto_mode(BUILD_VERSION, master_spec.major_minor, releases)
                    echo "BUILD_MODE = ${BUILD_MODE}"
                }
            }

            stage("analyze") {

                dir(env.OSE_DIR) {
                    // inputs:
                    //  IS_SOURCE_IN_MASTER
                    //  BUILD_MODE
                    //  BUILD_VERSION

                    // defines
                    //  BUILD_MODE (if auto)
                    //  OSE_SOURCE_BRANCH
                    //  UPSTREAM_SOURCE_BRANCH
                    //  NEW_VERSION
                    //  NEW_RELEASE
                    //  NEW_DOCKERFILE_RELEASE
                    //  USE_WEB_CONSOLE_SERVER
                    //
                    //  sets:
                    //    currentBuild.displayName

                    if (IS_SOURCE_IN_MASTER) {
                        if (BUILD_MODE == "release") {
                            error("You cannot build a release while it resides in master; cut an enterprise branch")
                        }
                    } else {
                        if (BUILD_MODE != "release" && BUILD_MODE != "pre-release") {
                            error("Invalid build mode for a release that does not reside in master: ${BUILD_MODE}")
                        }
                    }

                    if (IS_SOURCE_IN_MASTER) {
                        if (BUILD_MODE == "online:stg") {
                            OSE_SOURCE_BRANCH = "stage"
                            UPSTREAM_SOURCE_BRANCH = "upstream/stage"
                            sh "git checkout -b stage origin/stage"
                        } else {
                            OSE_SOURCE_BRANCH = "master"
                            UPSTREAM_SOURCE_BRANCH = "upstream/master"
                        }
                    } else {
                        OSE_SOURCE_BRANCH = "enterprise-${BUILD_VERSION}"
                        if (BUILD_MODE == "release") {
                            // When building in release mode, no longer pull from upstream
                            UPSTREAM_SOURCE_BRANCH = null
                        } else {
                            UPSTREAM_SOURCE_BRANCH = "upstream/release-${BUILD_VERSION}"
                        }
                        // Create the non-master source branch and have it track the origin ose repo
                        sh "git checkout -b ${OSE_SOURCE_BRANCH} origin/${OSE_SOURCE_BRANCH}"
                    }

                    echo "Building from ose branch: ${OSE_SOURCE_BRANCH}"

                    spec = buildlib.read_spec_info("origin.spec")
                    rel_fields = spec.release.tokenize(".")

                    if (! spec.version.startsWith("${BUILD_VERSION}.")) {
                        // Looks like pipeline thinks we are building something we aren't. Abort.
                        error("Expected version consistent with ${BUILD_VERSION}.* but found: ${spec.version}")
                    }


                    if (BUILD_MODE == "online:int" || BUILD_MODE == "online:stg") {
                        /**
                         * In non-release candidates, we need the following fields
                         *      REL.INT.STG
                         * REL = 0    means pre-release,  1 means release
                         * INT = fields used to differentiate online:int builds
                         * STG = fields used to differentiate online:stg builds
                         */

                        while (rel_fields.size() < 3) {
                            rel_fields << "0"    // Ensure there are enough fields in the array
                        }

                        if (rel_fields[0].toInteger() != 0) {
                            // Don't build release candidate images this way since they can't wind up
                            // in registry.access with a tag OCP can pull.
                            error("Do not build released products in ${BUILD_MODE}; just build in release or pre-release mode")
                        }

                        if (rel_fields.size() != 3) {
                            // Did we start with > 3? That's too weird to continue
                            error("Unexpected number of fields in release: ${spec.release}")
                        }

                        if (BUILD_MODE == "online:int") {
                            rel_fields[1] = rel_fields[1].toInteger() + 1  // Bump the INT version
                            rel_fields[2] = 0  // If we are bumping the INT field, everything following is reset to zero
                        }

                        if (BUILD_MODE == "online:stg") {
                            rel_fields[2] = rel_fields[2].toInteger() + 1  // Bump the STG version
                        }

                        NEW_VERSION = spec.version   // Keep the existing spec's version
                        NEW_RELEASE = "${rel_fields[0]}.${rel_fields[1]}.${rel_fields[2]}"

                        // Add a bumpable field for OIT to increment for image refreshes (i.e. REL.INT.STG.BUMP)
                        NEW_DOCKERFILE_RELEASE = "${NEW_RELEASE}.0"

                    } else if (BUILD_MODE == "release" || BUILD_MODE == "pre-release") {

                        /**
                         * Once someone sets the origin.spec Release to 1, we are building release candidates.
                         * If a release candidate is released, its associated images will show up in registry.access
                         * with the tags X.Y.Z-R  and  X.Y.Z. The "R" cannot be used since the fields is bumped by
                         * refresh-images when building images with signed RPMs. That is, if OCP tried to load images
                         * with the X.Y.Z-R' its RPM was built with, the R != R' (since R' < R) and the image
                         * would not be found.
                         * For release candidates, therefore, we must only use X.Y.Z to differentiate builds.
                         *
                         * Note that this problem does not affect online:int & online:stg builds since we control the
                         * tags in the registries. We have refresh-images bump a harmless field in the release and then
                         * craft a tag in the registry [version]-[release] which does not include that bumped field.
                         */
                        if (rel_fields[0].toInteger() != 1) {
                            error("You need to set the spec Release field to 1 in order to build in this mode")
                        }

                        // Undertake to increment the last field in the version (e.g. 3.7.0 -> 3.7.1)
                        ver_fields = spec.version.tokenize(".")
                        ver_fields[ver_fields.size() - 1] = "${ver_fields[ver_fields.size() - 1].toInteger() + 1}"
                        NEW_VERSION = ver_fields.join(".")
                        NEW_RELEASE = "1"
                        NEW_DOCKERFILE_RELEASE = NEW_RELEASE

                    } else {
                        error("Unknown BUILD_MODE: ${BUILD_MODE}")
                    }

                    // decide which source to use for the web console
                    USE_WEB_CONSOLE_SERVER = false
                    if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR >= 9) {
                        USE_WEB_CONSOLE_SERVER = true
                    }

                    rpmOnlyTag = ""
                    if (!BUILD_CONTAINER_IMAGES) {
                        rpmOnlyTag = " (RPM ONLY)"
                    }
                    currentBuild.displayName = "#${currentBuild.number} - ${NEW_VERSION}-${NEW_RELEASE} (${BUILD_MODE}${rpmOnlyTag})"
                }
            }

            stage("merge origin") {
                dir(OSE_DIR) {
                    // Enable fake merge driver used in our .gitattributes
                    sh "git config merge.ours.driver true"
                    // Use fake merge driver on specific packages
                    sh "echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes"
                    sh "echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes"

                    if (UPSTREAM_SOURCE_BRANCH != null) {
                        // Merge upstream origin code into the ose branch
                        sh "git merge -m 'Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}' ${UPSTREAM_SOURCE_BRANCH}"
                    } else {
                        echo "No origin upstream in this build"
                    }
                }
            }

            stage("origin-web-console repo") {
                sh "go get github.com/jteeuwen/go-bindata"
                // defines:
                //   WEB_CONSOLE_DIR
                //   GITHUB_URLS["origin-web-console"]
                //   GITHUB_BASE_PATHS["origin-web-console"]
                buildlib.initialize_origin_web_console()
                dir(WEB_CONSOLE_DIR) {
                    // Enable fake merge driver used in our .gitattributes
                    sh "git config merge.ours.driver true"
                    // Use fake merge driver on specific directories
                    // We will be re-generating the dist directory, so ignore it for the merge
                    sh "echo 'dist/** merge=ours' >> .gitattributes"
                }
            }

            stage("prep web-console") {
                dir(WEB_CONSOLE_DIR) {
                    // Unless building for stage, origin-web-console#entperise-X.Y should be used
                    if (BUILD_MODE == "online:stg") {
                        WEB_CONSOLE_BRANCH = "stage"
                        sh "git checkout -b stage origin/stage"
                    } else {
                        WEB_CONSOLE_BRANCH = "enterprise-${spec.major_minor}"
                        sh "git checkout -b ${WEB_CONSOLE_BRANCH} origin/${WEB_CONSOLE_BRANCH}"
                        if (IS_SOURCE_IN_MASTER) {

                            // jwforres asked that master *not* merge into the 3.8 branch.
                            if (BUILD_VERSION != "3.8") {
                                sh """
                                # Pull content of master into enterprise branch
                                git merge master --no-commit --no-ff
                                # Use grunt to rebuild everything in the dist directory
                                ./hack/install-deps.sh
                                grunt build

                                git add dist
                                git commit -m "Merge master into enterprise-${BUILD_VERSION}" --allow-empty
                            """

                                if (!IS_TEST_MODE) {
                                    sh "git push"
                                }
                            }

                        }
                    }

                    // Clean up any unstaged changes (e.g. .gitattributes)
                    sh "git reset --hard HEAD"
                }
            }


            stage("origin-web-console-server repo") {
                /**
                 * The origin-web-console-server repo/image was introduced in 3.9.
                 */
                if (USE_WEB_CONSOLE_SERVER) {
                    // defines:
                    //   WEB_CONSOLE_SERVER_DIR
                    //   GITHUB_URLS["origin-web-console-server"]
                    //   GITHUB_BASE_PATHS["origin-web-console-server"]
                    buildlib.initialize_origin_web_console_server_dir()
                    if (BUILD_MODE == "online:stg") {
                        WEB_CONSOLE_SERVER_BRANCH = "stage"
                    } else {
                        WEB_CONSOLE_SERVER_BRANCH = "enterprise-${BUILD_VERSION_MAJOR}.${BUILD_VERSION_MINOR}"
                    }
                    dir(WEB_CONSOLE_SERVER_DIR) {
                        sh "git checkout ${WEB_CONSOLE_SERVER_BRANCH}"
                    }
                }
            }

            stage("prep web-console-server") {
                if (BUILD_MODE != "online:stg" && USE_WEB_CONSOLE_SERVER && IS_SOURCE_IN_MASTER) {
                    dir(WEB_CONSOLE_SERVER_DIR) {
                        // Enable fake merge driver used in our .gitattributes
                        sh "git config merge.ours.driver true"
                        // Use fake merge driver on specific packages
                        sh "echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes"
                        sh "echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes"


                        sh """
                            # Pull content of master into enterprise branch
                            git merge master --no-commit --no-ff
                            git commit -m "Merge master into enterprise-${BUILD_VERSION}" --allow-empty
                        """

                        if (!IS_TEST_MODE) {
                            sh "git push"
                        }

                        // Clean up any unstaged changes (e.g. .gitattributes)
                        sh "git reset --hard HEAD"
                    }
                }
            }

            stage("merge web-console") {

                // In OCP release < 3.9, web-console is vendored into OSE repo
                TARGET_VENDOR_DIR = OSE_DIR
                if (USE_WEB_CONSOLE_SERVER) {
                    // In OCP release > 3.9, web-console is vendored into origin-web-console-server
                    TARGET_VENDOR_DIR = WEB_CONSOLE_SERVER_DIR
                }

                dir(TARGET_VENDOR_DIR) {

                    // Vendor a particular branch of the web console into our ose branch and capture the SHA we vendored in
                    // TODO: Is this necessary? If we don't specify a GIT_REF, will it just use the current branch
                    // we already setup?
                    // TODO: Easier way to get the VC_COMMIT by just using parse-rev when we checkout the desired web console branch?
                    VC_COMMIT = sh(
                        returnStdout: true,
                        script: "GIT_REF=${WEB_CONSOLE_BRANCH} hack/vendor-console.sh 2>/dev/null | grep 'Vendoring origin-web-console' | awk '{print \$4}'",
                    ).trim()

                    if (VC_COMMIT == "") {
                        sh("GIT_REF=${WEB_CONSOLE_BRANCH} hack/vendor-console.sh 2>/dev/null")
                        error("Unable to acquire VC_COMMIT")
                    }

                    // Vendoring the console will rebuild this assets, so add them to the commit
                    sh """
                    git add pkg/assets/bindata.go
                    git add pkg/assets/java/bindata.go
                """

                    if (USE_WEB_CONSOLE_SERVER && !IS_TEST_MODE) {
                        sh "git commit -m 'bump origin-web-console ${VC_COMMIT}' --allow-empty"
                        sh "git push"
                    }
                }

            }

            stage("openshift-ansible repo") {
                buildlib.initialize_openshift_ansible()
            }

            stage("openshift-ansible prep") {
                OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "master"
                dir(OPENSHIFT_ANSIBLE_DIR) {
                    if (BUILD_MODE == "online:stg") {
                        sh "git checkout -b stage origin/stage"
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "stage"
                    } else {
                        if (!IS_SOURCE_IN_MASTER) {
                            // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                            if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                                OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                            } else {
                                OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${BUILD_VERSION}"
                            }
                            sh "git checkout -b ${OPENSHIFT_ANSIBLE_SOURCE_BRANCH} origin/${OPENSHIFT_ANSIBLE_SOURCE_BRANCH}"
                        } else {
                            sh "git checkout master"
                        }
                    }
                }
            }

            // stages after this have side effects. Testing must stop here.
            if (IS_TEST_MODE) {
                echo(
                    "TEST MODE complete: no builds executed")
                currentBuild.result = "SUCCESS"
                return
            }

            stage("ose tag") {
                dir(OSE_DIR) {
                    // Set the new version/release value in the file and tell tito to keep the version & release in the spec.
                    buildlib.set_rpm_spec_version("origin.spec", NEW_VERSION)
                    buildlib.set_rpm_spec_release_prefix("origin.spec", NEW_RELEASE)
                    // Note that I did not use --use-release because it did not maintain variables like %{?dist}

                    commit_msg = "Automatic commit of package [atomic-openshift] release [${NEW_VERSION}-${NEW_RELEASE}]"
                    if (!USE_WEB_CONSOLE_SERVER) {
                        // If vendoring web console into ose, include the VC_COMMIT information in the ose commit
                        commit_msg = "${commit_msg} ; bump origin-web-console ${VC_COMMIT}"
                    }

                    sh "git commit --allow-empty -m '${commit_msg}'" // add commit to capture our change message
                    sh "tito tag --accept-auto-changelog --keep-version --debug"
                    if (!IS_TEST_MODE) {
                        sh "git push"
                        sh "git push --tags"
                    }
                    OSE_CHANGELOG = buildlib.read_changelog("origin.spec")
                }
            }

            stage("openshift-ansible tag") {
                dir(OPENSHIFT_ANSIBLE_DIR) {
                    if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                        // Use legacy versioning if < 3.6
                        sh "tito tag --debug --accept-auto-changelog"
                    } else {
                        // If >= 3.6, keep openshift-ansible in sync with OCP version
                        buildlib.set_rpm_spec_version("openshift-ansible.spec", NEW_VERSION)
                        buildlib.set_rpm_spec_release_prefix("openshift-ansible.spec", NEW_RELEASE)
                        // Note that I did not use --use-release because it did not maintain variables like %{?dist}
                        sh "tito tag --debug --accept-auto-changelog --keep-version --debug"

                    }
                    if (!IS_TEST_MODE) {
                        sh "git push"
                        sh "git push --tags"
                    }
                    OA_CHANGELOG = buildlib.read_changelog("openshift-ansible.spec")
                }
            }

            stage("rpm builds") {
                // Allow both brew builds to run at the same time

                dir(OSE_DIR) {
                    OSE_TASK_ID = sh(
                        returnStdout: true,
                        script: "tito release --debug --yes --test aos-${BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                    )
                    OSE_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${OSE_TASK_ID}"
                    echo "ose rpm brew task: ${OSE_BREW_URL}"
                }

                dir(OPENSHIFT_ANSIBLE_DIR) {
                    OA_TASK_ID = sh(
                        returnStdout: true,
                        script: "tito release --debug --yes --test aos-${BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                    )
                    OA_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${OA_TASK_ID}"
                    echo "openshift-ansible rpm brew task: ${OA_BREW_URL}"
                }

                // Watch the tasks to make sure they succeed. If one fails, make sure the user knows which one by providing the correct brew URL
                try {
                    sh "brew watch-task ${OSE_TASK_ID}"
                } catch (ose_err) {
                    echo "Error in ose build task: ${OSE_BREW_URL}"
                    throw ose_err
                }

                try {
                    sh "brew watch-task ${OA_TASK_ID}"
                } catch (oa_err) {
                    echo "Error in openshift-ansible build task: ${OA_BREW_URL}"
                    throw oa_err
                }
            }

            buildlib.write_sources_file()


            // at this point we need both the OIT tools and the groups database
            stage("enterprise-images repo") {
                // defines
                //   ENTERPRISE_IMAGES_DIR
                //   OIT_PATH
                buildlib.initialize_enterprise_images_dir()
            }

            stage("build OIT rpms") {
                buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${BUILD_VERSION}'
--sources ${env.WORKSPACE}/sources.yml
rpms:build --version v${NEW_VERSION}
--release ${NEW_RELEASE}
"""
            }

            stage("signing rpms") {
                if (SIGN_RPMS) {
                    sh "${env.WORKSPACE}/build-scripts/sign_rpms.sh rhaos-${BUILD_VERSION}-rhel-7-candidate openshifthosted"
                } else {
                    echo "RPM signing has been skipped..."
                }
            }

            stage("puddle: ose 'building'") {
                OCP_PUDDLE = buildlib.build_puddle(
                    PUDDLE_CONF,    // The puddle configuration file to use
                    PUDDLE_SIGN_KEYS, // openshifthosted key
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n",   // do not send an email for this puddle
                    "-s",   // do not create a "latest" link since this puddle is for building images
                    "--label=building"   // create a symlink named "building" for the puddle
                )
            }

            stage("update dist-git") {
                buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${BUILD_VERSION}'
--sources ${env.WORKSPACE}/sources.yml
${ODCS_FLAG}
images:rebase --version v${NEW_VERSION}
--release ${NEW_DOCKERFILE_RELEASE}
--message 'Updating Dockerfile version and release v${NEW_VERSION}-${NEW_DOCKERFILE_RELEASE}' --push
"""
            }

            record_log = buildlib.parse_record_log(OIT_WORKING)
            distgit_notify = buildlib.get_distgit_notify(record_log)
            distgit_notify = buildlib.mapToList(distgit_notify)
            // loop through all new commits and notify their owners

            SOURCE_BRANCHES = [
                "ose"              : OSE_SOURCE_BRANCH,
                "openshift-ansible": OPENSHIFT_ANSIBLE_SOURCE_BRANCH
            ]
            for (i = 0; i < distgit_notify.size(); i++) {
                distgit = distgit_notify[i][0]
                val = distgit_notify[i][1]

                try {
                    alias = val['source_alias']
                    dockerfile_url = ""
                    github_url = GITHUB_URLS[alias]
                    github_url = github_url.replace(".git", "")
                    github_url = github_url.replace("git@", "")
                    github_url = github_url.replaceFirst(":", "/")
                    dockerfile_sub_path = val['source_dockerfile_subpath']
                    dockerfile_url = "Upstream source file: https://" + github_url + "/blob/" + SOURCE_BRANCHES[alias] + "/" + dockerfile_sub_path
                    try {
                        // always mail success list, val.owners will be comma delimited or empty
                        mail(
                            to: "aos-team-art@redhat.com,${val.owners}",
                            from: "aos-cicd@redhat.com",
                            subject: "${val.image} Dockerfile reconciliation for OCP v${BUILD_VERSION}",
                            body: """
Why am I receiving this?
You are receiving this message because you are listed as an owner for an OpenShift related image - or
you recently made a modification to the definition of such an image in github. Upstream OpenShift Dockerfiles
(e.g. those in the openshift/origin repository under images/*) are regularly pulled from their upstream
source and used as an input to build our productized images - RHEL based OpenShift Container Platform (OCP) images.

To serve as an input to RHEL/OCP images, upstream Dockerfiles are programmatically modified before they are checked
into a downstream git repository which houses all Red Hat images: http://dist-git.host.prod.eng.bos.redhat.com/cgit/rpms/ .
We call this programmatic modification "reconciliation" and you will receive an email each time the upstream
Dockerfile changes so that you can review the differences between the upstream & downstream Dockerfiles.


What do I need to do?
You may want to look at the result of the reconciliation. Usually, reconciliation is transparent and safe.
However, you may be interested in any changes being performed by the OCP build system.


What changed this time?
Reconciliation has just been performed for the image: ${val.image}
${dockerfile_url}

The reconciled (downstream OCP) Dockerfile can be view here: https://pkgs.devel.redhat.com/cgit/${distgit}/tree/Dockerfile?id=${val.sha}

Please direct any questsions to the Continuous Delivery team (#aos-cd-team on IRC).
                """);
                    } catch (err) {

                        echo "Failure sending email"
                        echo "${err}"
                    }
                } catch (err_alias) {

                    echo "Failure resolving alias for email"
                    echo "${err_alias}"
                }
            }

            BUILD_CONTINUED = false
            stage("build images") {
                if (BUILD_CONTAINER_IMAGES) {

                    waitUntil {
                        try {
                            exclude = ""
                            if (BUILD_EXCLUSIONS != "") {
                                exclude = "-x ${BUILD_EXCLUSIONS} --ignore-missing-base"
                            }
                            buildlib.oit """
    --working-dir ${OIT_WORKING} --group openshift-${BUILD_VERSION}
    ${ODCS_FLAG}
    ${exclude}
    images:build
    --push-to-defaults --repo-type unsigned ${ODCS_OPT}
    """
                            return true // finish waitUntil
                        }
                        catch (err) {
                            failed_map = buildlib.get_failed_builds(OIT_WORKING)

                            mail(to: "${MAIL_LIST_FAILURE}",
                                 from: "aos-cicd@redhat.com",
                                 subject: "RESUMABLE Error during Image Build for OCP v${BUILD_VERSION}",
                                 body: """Encountered an error: ${err}
    Input URL: ${env.BUILD_URL}input
    Jenkins job: ${env.BUILD_URL}

    BUILD / PUSH FAILURES:
    ${failed_map}
    """);

                            def resp = input(
                                message: "Error during Image Build for OCP v${BUILD_VERSION}",
                                parameters: [
                                    [
                                        $class     : 'hudson.model.ChoiceParameterDefinition',
                                        choices    : "RETRY\nCONTINUE\nABORT",
                                        description: 'Retry (try the operation again). Continue (fails are OK, continue pipeline). Abort (terminate the pipeline).',
                                        name       : 'action'
                                    ]
                                ]
                            )

                            if (resp == "RETRY") {
                                return false  // cause waitUntil to loop again
                            } else if (resp == "CONTINUE") {
                                echo "User chose to continue. Build failures are non-fatal."
                                BUILD_EXCLUSIONS = failed_map.keySet().join(",") //will make email show PARTIAL
                                BUILD_CONTINUED = true //simply setting flag to keep required work out of input flow
                                return true // Terminate waitUntil
                            } else {
                                // ABORT
                                error("User chose to abort pipeline because of image build failures")
                            }
                        }
                    }

                    if (BUILD_CONTINUED) {
                        buildlib.oit """
    --working-dir ${OIT_WORKING} --group openshift-${BUILD_VERSION}
    ${exclude} images:push --to-defaults --late-only
    """
                        // exclude is already set earlier in the main images:build flow
                    }
                }
            }

            NEW_FULL_VERSION = "${NEW_VERSION}-${NEW_RELEASE}"

            SYMLINK_NAME = "latest"
            if (!BUILD_CONTAINER_IMAGES) {
                SYMLINK_NAME = "no-image-latest"
            }

            // Push the building puddle out to the correct directory on the mirrors (e.g. online-int, online-stg, or enterprise-X.Y)
            buildlib.invoke_on_rcm_guest("push-to-mirrors.sh", SYMLINK_NAME, NEW_FULL_VERSION, BUILD_MODE)

            // push-to-mirrors.sh sets up a different puddle name on rcm-guest and the mirrors
            OCP_PUDDLE = "v${NEW_FULL_VERSION}_${OCP_PUDDLE}"
            final mirror_url = get_mirror_url(BUILD_MODE, BUILD_VERSION)

            stage("ami") {
                if (params.BUILD_AMI && BUILD_CONTAINER_IMAGES) {
                    // define openshift ansible source branch
                    OPENSHIFT_ANSIBLE_SOURCE_BRANCH = 'master'
                    if (BUILD_MODE == 'online:stg') {
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = 'stage'
                    } else {
                        if (!IS_SOURCE_IN_MASTER) {
                            // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                            if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                                OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                            } else {
                                OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${BUILD_VERSION}"
                            }
                        }
                    }
                    buildlib.build_ami(
                        BUILD_VERSION_MAJOR, BUILD_VERSION_MINOR,
                        NEW_VERSION, NEW_RELEASE,
                        "${mirror_url}/${OCP_PUDDLE}/x86_64/os",
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH,
                        MAIL_LIST_FAILURE)
                }
            }

            if (NEW_RELEASE != "1") {
                // If this is not a release candidate, push binary in a directory qualified with release field information
                buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", BUILD_VERSION, NEW_FULL_VERSION)
            } else {
                // If this is a release candidate, the directory binary directory should not contain release information
                buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", BUILD_VERSION, NEW_VERSION)
            }

            echo "Finished building OCP ${NEW_FULL_VERSION}"
            PREV_BUILD = null  // We are done. Don't untag even if there is an error sending the email.

            // Don't make an github release unless this build it from the actual ose repo
            if ( GITHUB_BASE == "git@github.com:openshift" ) {
                try {
                    withCredentials([string(credentialsId: 'github_token_ose', variable: 'GITHUB_TOKEN')]) {
                        httpRequest(
                            consoleLogResponseBody: true,
                            httpMode: 'POST',
                            ignoreSslErrors: true,
                            responseHandle: 'NONE',
                            url: "https://api.github.com/repos/openshift/ose/releases?access_token=${GITHUB_TOKEN}",
                            requestBody: """{"tag_name": "v${NEW_VERSION}-${NEW_RELEASE}",
"target_commitish": "${OSE_SOURCE_BRANCH}",
"name": "v${NEW_VERSION}-${NEW_RELEASE}",
"draft": true,
"prerelease": false,
"body": "Release of OpenShift Container Platform v${NEW_VERSION}-${NEW_RELEASE}\\nPuddle: ${mirror_url}/${OCP_PUDDLE}"
}"""
                        )
                    }

                } catch( release_ex ) {
                    mail(
                        to: "aos-team-art@redhat.com",
                        from: "aos-cicd@redhat.com",
                        subject: "Error creating ose release in github",
                        body: """
Jenkins job: ${env.BUILD_URL}
"""
                    );
                }
            }
            mail_success(NEW_FULL_VERSION, mirror_url, record_log, OA_CHANGELOG)
        }
    } catch (err) {

        ATTN = ""
        try {
            NEW_BUILD = sh(returnStdout: true, script: "brew latest-build --quiet rhaos-${BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()
            if (PREV_BUILD != null && PREV_BUILD != NEW_BUILD) {
                // Untag anything tagged by this build if an error occured at any point
                sh "brew --user=ocp-build untag-build rhaos-${BUILD_VERSION}-rhel-7-candidate ${NEW_BUILD}"
            }
        } catch (err2) {
            ATTN = " - UNABLE TO UNTAG!"
        }

        mail(to: "${MAIL_LIST_FAILURE}",
             from: "aos-cicd@redhat.com",
             subject: "Error building OSE: ${BUILD_VERSION}${ATTN}",
             body: """Encountered an error while running OCP pipeline: ${err}

    Jenkins job: ${env.BUILD_URL}
    """);
        throw err
    } finally {
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/*.log"
            archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/brew-logs/**"
        } catch (aae) {
        }
    }
}
