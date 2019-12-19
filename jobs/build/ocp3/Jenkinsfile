#!/usr/bin/env groovy


def get_mirror_url(build_mode, version) {
    if (build_mode == "online:int") {
        return "https://mirror.openshift.com/enterprise/online-int"
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
                "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew buildinfo ${build_id} --changelog",
                "sed -n '/Changelog/,\$p'"
            ].join(' | ')
        ).trim()
    } catch (err) {
        error "failed to get build info and changelog for build ${build_id}"
    }

    return changelog
}

def mail_success(version, mirrorURL, record_log, oa_changelog, commonlib) {

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
        from: "aos-art-automation@redhat.com",
        replyTo: "aos-team-art@redhat.com",
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
        if (BUILD_EXCLUSIONS == "" && params.BUILD_CONTAINER_IMAGES) {
            timeout(3) {
                sendCIMessage(
                    messageContent: "New build for OpenShift ${target}: ${version}",
                    messageProperties:
                        """build_mode=${BUILD_MODE}
                        PUDDLE_URL=${mirrorURL}/${OCP_PUDDLE}
                        IMAGE_REGISTRY_ROOT=registry.reg-aws.openshift.com:443
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
                    [
                        name: 'SSH_KEY_ID',
                        description: 'SSH credential id to use',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "openshift-bot",
                            "aos-cd-test",
                            "adammhaile-aos-cd-bot",
                        ].join("\n"),
                        defaultValue: 'aos-cd-test'
                    ],
                    commonlib.ocpVersionParam('BUILD_VERSION', '3'),
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-art-automation+new-ocp3-build@redhat.com',
                        ].join(',')
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-ocp3-build@redhat.com'
                        ].join(',')
                    ],
                    [
                        name: 'BUILD_MODE',
                        description: '''
    auto                      BUILD_VERSION and ocp repo contents determine the mode<br>
    release                   {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
    pre-release               {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
    online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
    ''',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "auto",
                            "release",
                            "pre-release",
                            "online:int"
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
                    commonlib.mockParam(),
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

    IS_TEST_MODE = params.TEST
    buildlib.initialize(IS_TEST_MODE)

    BUILD_VERSION_MAJOR = params.BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    BUILD_VERSION_MINOR = params.BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y
    SIGN_RPMS = params.SIGN
    ODCS_MODE = params.ODCS
    ODCS_FLAG = ""
    ODCS_OPT = ""
    if (ODCS_MODE) {
        ODCS_FLAG = "--odcs-mode"
        ODCS_OPT = "--odcs unsigned"
    }

    BUILD_EXCLUSIONS = commonlib.cleanCommaList(params.BUILD_EXCLUSIONS)
    BUILD_FAILURES = null

    // Will be used to track which atomic-openshift build was tagged before we ran.
    PREV_BUILD = null

    aosCdJobsCommitSha = sh(
        returnStdout: true,
        script: "git rev-parse HEAD",
    ).trim()

    try {
        // Clean up old images so that we don't run out of device mapper space
        sh "docker rmi --force \$(docker images  | grep v${params.BUILD_VERSION} | awk '{print \$3}')"
    } catch (cce) {
        echo "Error cleaning up old images: ${cce}"
    }

    puddleConfBase = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/${aosCdJobsCommitSha}/build-scripts/puddle-conf"
    puddleConf = "${puddleConfBase}/atomic_openshift-${params.BUILD_VERSION}.conf"
    puddleSignKeys = SIGN_RPMS ? "b906ba72" : null

    echo "Initializing build: #${currentBuild.number} - ${params.BUILD_VERSION}.?? (${BUILD_MODE})"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(DOOZER_WORKING)

    try {
        sshagent([params.SSH_KEY_ID]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot

            PREV_BUILD = sh(
                returnStdout: true,
                script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew latest-build --quiet rhaos-${params.BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'"
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
                // If the target version resides in ose#master
                IS_SOURCE_IN_MASTER = false  // master is of no concern for 3.x ever again

                if (BUILD_MODE == "auto") {
                    echo "AUTO-MODE: determine mode from version and repo: BUILD_VERSION: ${params.BUILD_VERSION}"
                    // INPUTS:
                    //   BUILD_MODE
                    //   BUILD_VERSION
                    //   GITHUB_URLS["ose"]
                    releases = buildlib.get_releases(GITHUB_URLS['ose'])
                    echo "AUTO-MODE: release repo: ${GITHUB_URLS['ose']}"
                    echo "AUTO-MODE: releases: ${releases}"
                    BUILD_MODE = buildlib.auto_mode(params.BUILD_VERSION, '4.0', releases)
                    echo "BUILD_MODE = ${BUILD_MODE}"
                }
            }

            stage("analyze") {

                dir(OSE_DIR) {
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
                        OSE_SOURCE_BRANCH = "master"
                        UPSTREAM_SOURCE_BRANCH = "upstream/master"
                    } else {
                        OSE_SOURCE_BRANCH = "enterprise-${params.BUILD_VERSION}"
                        if (BUILD_MODE == "release") {
                            // When building in release mode, no longer pull from upstream
                            UPSTREAM_SOURCE_BRANCH = null
                        } else {
                            UPSTREAM_SOURCE_BRANCH = "upstream/release-${params.BUILD_VERSION}"
                        }
                        // Create the non-master source branch and have it track the origin ose repo
                        sh "git checkout -B ${OSE_SOURCE_BRANCH} origin/${OSE_SOURCE_BRANCH}"
                    }

                    echo "Building from ose branch: ${OSE_SOURCE_BRANCH}"

                    spec = buildlib.read_spec_info("origin.spec")
                    rel_fields = spec.release.tokenize(".")

                    if (! spec.version.startsWith("${params.BUILD_VERSION}.")) {
                        // Looks like pipeline thinks we are building something we aren't. Abort.
                        error("Expected version consistent with ${params.BUILD_VERSION}.* but found: ${spec.version}")
                    }


                    if (BUILD_MODE == "online:int") {
                        /**
                         * In non-release candidates, we need the following fields
                         *      REL.INT.STG
                         * REL = 0    means pre-release,  1 means release
                         * INT = fields used to differentiate online:int builds
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

                        NEW_VERSION = spec.version   // Keep the existing spec's version
                        NEW_RELEASE = "${rel_fields[0]}.${rel_fields[1]}.${rel_fields[2]}"

                        // Add a bumpable field for Doozer to increment for image refreshes (i.e. REL.INT.STG.BUMP)
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
                    if (!params.BUILD_CONTAINER_IMAGES) {
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
                if (BUILD_VERSION_MAJOR != 3) return

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
                if (BUILD_VERSION_MAJOR != 3) return

                dir(WEB_CONSOLE_DIR) {
                    WEB_CONSOLE_BRANCH = "enterprise-${spec.major_minor}"
                    sh "git checkout -B ${WEB_CONSOLE_BRANCH} origin/${WEB_CONSOLE_BRANCH}"
                    if (IS_SOURCE_IN_MASTER) {

                        // jwforres asked that master *not* merge into the 3.8 branch.
                        if (params.BUILD_VERSION != "3.8") {
                            sh """
                            # Pull content of master into enterprise branch
                            git merge master --no-commit --no-ff
                            # Use grunt to rebuild everything in the dist directory
                            ./hack/install-deps.sh
                            grunt build

                            git add dist
                            git commit -m "Merge master into enterprise-${params.BUILD_VERSION}" --allow-empty
                        """

                            if (!IS_TEST_MODE) {
                                sh "git push"
                            }
                        }

                    }

                    // Clean up any unstaged changes (e.g. .gitattributes)
                    sh "git reset --hard HEAD"
                }
            }


            stage("origin-web-console-server repo") {
                if (BUILD_VERSION_MAJOR != 3) return

                /**
                * The origin-web-console-server repo/image was introduced in 3.9.
                */
                if (USE_WEB_CONSOLE_SERVER) {
                    // defines:
                    //   WEB_CONSOLE_SERVER_DIR
                    //   GITHUB_URLS["origin-web-console-server"]
                    //   GITHUB_BASE_PATHS["origin-web-console-server"]
                    buildlib.initialize_origin_web_console_server_dir()
                    WEB_CONSOLE_SERVER_BRANCH = "enterprise-${BUILD_VERSION_MAJOR}.${BUILD_VERSION_MINOR}"
                    dir(WEB_CONSOLE_SERVER_DIR) {
                        sh "git checkout ${WEB_CONSOLE_SERVER_BRANCH}"
                    }
                }
            }

            stage("prep web-console-server") {
                if (BUILD_VERSION_MAJOR != 3) return

                if (USE_WEB_CONSOLE_SERVER && IS_SOURCE_IN_MASTER) {
                    dir(WEB_CONSOLE_SERVER_DIR) {
                        // Enable fake merge driver used in our .gitattributes
                        sh "git config merge.ours.driver true"
                        // Use fake merge driver on specific packages
                        sh "echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes"
                        sh "echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes"


                        sh """
                            # Pull content of master into enterprise branch
                            git merge master --no-commit --no-ff
                            git commit -m "Merge master into enterprise-${params.BUILD_VERSION}" --allow-empty
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
                if (BUILD_VERSION_MAJOR != 3) return

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
                    if (!IS_SOURCE_IN_MASTER) {
                        // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                        if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                        } else {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${params.BUILD_VERSION}"
                        }
                        sh "git checkout -B ${OPENSHIFT_ANSIBLE_SOURCE_BRANCH} origin/${OPENSHIFT_ANSIBLE_SOURCE_BRANCH}"
                    } else {
                        sh "git checkout master"
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
                    if (BUILD_VERSION_MAJOR == 3 && !USE_WEB_CONSOLE_SERVER) {
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
                    oseTaskId = sh(
                        returnStdout: true,
                        script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt tito release --debug --yes --test aos-${params.BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                    )
                    OSE_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${oseTaskId }"
                    echo "atomic-openshift rpm brew task: ${OSE_BREW_URL}"
                }

                dir(OPENSHIFT_ANSIBLE_DIR) {
                    oaTaskId = sh(
                        returnStdout: true,
                        script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt tito release --debug --yes --test aos-${params.BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                    )
                    OA_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${oaTaskId}"
                    echo "openshift-ansible rpm brew task: ${OA_BREW_URL}"
                }

                // [lmeyer Apr 2019] this would be nice in parallel except that
                // commonlib.shell turns out not to be safe for concurrency. Keep it serial for now.
                buildlib.watch_brew_task_and_retry("atomic-openshift RPM", oseTaskId, OSE_BREW_URL)
                buildlib.watch_brew_task_and_retry("openshift-ansible RPM", oaTaskId, OA_BREW_URL)
            }

            stage("doozer build rpms") {
                buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group 'openshift-${params.BUILD_VERSION}'
--source ose ${OSE_DIR}
rpms:build --version v${NEW_VERSION}
--release ${NEW_RELEASE}
"""
            }

            stage("signing rpms") {
                if (SIGN_RPMS) {
                    sh "${env.WORKSPACE}/build-scripts/sign_rpms.sh rhaos-${params.BUILD_VERSION}-rhel-7-candidate openshifthosted"
                } else {
                    echo "RPM signing has been skipped..."
                }
            }

            stage("puddle: ose 'building'") {
                OCP_PUDDLE = buildlib.build_puddle(
                    puddleConf,    // The puddle configuration file to use
                    puddleSignKeys, // openshifthosted key
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n",   // do not send an email for this puddle
                    "-s",   // do not create a "latest" link since this puddle is for building images
                    "--label=building"   // create a symlink named "building" for the puddle
                )
            }

            stage("update dist-git") {
                buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group 'openshift-${params.BUILD_VERSION}'
--source ose ${OSE_DIR}
${ODCS_FLAG}
images:rebase --version v${NEW_VERSION}
--release ${NEW_DOCKERFILE_RELEASE}
--message 'Updating Dockerfile version and release v${NEW_VERSION}-${NEW_DOCKERFILE_RELEASE}' --push
"""
                buildlib.notify_dockerfile_reconciliations(DOOZER_WORKING, params.BUILD_VERSION)
            }

            stage("build images") {
                if (params.BUILD_CONTAINER_IMAGES) {
                    try {
                        exclude = ""
                        if (BUILD_EXCLUSIONS != "") {
                            exclude = "-x ${BUILD_EXCLUSIONS} --ignore-missing-base"
                        }
                        buildlib.doozer """
--working-dir ${DOOZER_WORKING} --group openshift-${params.BUILD_VERSION}
${ODCS_FLAG}
${exclude}
images:build
--push-to-defaults --repo-type unsigned ${ODCS_OPT}
"""
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

            stage("ami") {
                if (params.BUILD_AMI && params.BUILD_CONTAINER_IMAGES) {
                    // define openshift ansible source branch
                    OPENSHIFT_ANSIBLE_SOURCE_BRANCH = 'master'
                    if (!IS_SOURCE_IN_MASTER) {
                        // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                        if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                        } else {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${params.BUILD_VERSION}"
                        }
                    }
                    buildlib.build_ami(
                        BUILD_VERSION_MAJOR, BUILD_VERSION_MINOR,
                        NEW_VERSION, NEW_RELEASE,
                        "${mirror_url}/${OCP_PUDDLE}/x86_64/os",
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH,
                        params.MAIL_LIST_FAILURE)
                }
            }

            if (NEW_RELEASE != "1") {
                // If this is not a release candidate, push binary in a directory qualified with release field information
                buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", params.BUILD_VERSION, NEW_FULL_VERSION)
            } else {
                // If this is a release candidate, the directory binary directory should not contain release information
                buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", params.BUILD_VERSION, NEW_VERSION)
            }

            echo "Finished building OCP ${NEW_FULL_VERSION}"
            PREV_BUILD = null  // We are done. Don't untag even if there is an error sending the email.
            mail_success(NEW_FULL_VERSION, mirror_url, record_log, OA_CHANGELOG, commonlib)
        }
    } catch (err) {

        ATTN = ""
        try {
            NEW_BUILD = sh(returnStdout: true, script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew latest-build --quiet rhaos-${params.BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()
            if (PREV_BUILD != null && PREV_BUILD != NEW_BUILD) {
                // Untag anything tagged by this build if an error occured at any point
                sh "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew --user=ocp-build untag-build rhaos-${params.BUILD_VERSION}-rhel-7-candidate ${NEW_BUILD}"
            }
        } catch (err2) {
            ATTN = " - UNABLE TO UNTAG!"
        }

        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error building OSE: ${params.BUILD_VERSION}${ATTN}",
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
