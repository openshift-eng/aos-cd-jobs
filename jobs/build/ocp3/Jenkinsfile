#!/usr/bin/env groovy


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
    Plashet (internal): http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${params.BUILD_VERSION}/${PLASHET}
    Exernal Mirror: ${mirrorURL}/${PLASHET}
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
                        PUDDLE_URL=${mirrorURL}/${PLASHET}
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
    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("ocp3", """
        <h2>Create a full OCP 3.11 dev build</h2>
        <b>Timing</b>: Run nightly by scheduled job (when not disabled).
        Humans might run if that didn't work properly or recently enough.

        This is a monolithic 3.11 build. All RPMs and images are built with the
        next 3.11.z version, which is required for the installer to deploy as a
        coherent release. An RPM compose is created and synced for testing and SD.
        The whole thing must complete to be considered a success.
    """)


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
                    choice(
                        name: 'SSH_KEY_ID',
                        description: 'SSH credential id to use',
                        choices: [
                            "openshift-bot",
                        ].join("\n"),
                    ),
                    commonlib.ocpVersionParam('BUILD_VERSION', '3'),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-art-automation+new-ocp3-build@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-ocp3-build@redhat.com'
                        ].join(','),
                        trim: true,
                    ),
                    booleanParam(
                        name: 'ODCS',
                        description: 'Run in ODCS Mode?',
                        defaultValue: false,
                    ),
                    string(
                        name: 'SPECIAL_NOTES',
                        description: 'Include special notes in the build email',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'BUILD_EXCLUSIONS',
                        description: 'Exclude these images from builds. Comma or space separated list. (i.e cri-o-docker,aos3-installation-docker)',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'BUILD_CONTAINER_IMAGES',
                        description: 'Build container images?',
                        defaultValue: true,
                    ),
                    booleanParam(
                        name: 'BUILD_AMI',
                        description: 'Build golden image after building images?',
                        defaultValue: true,
                    ),
                    commonlib.mockParam(),
                    commonlib.dryrunParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    IS_TEST_MODE = params.DRY_RUN ?: false
    buildlib.initialize(IS_TEST_MODE)

    BUILD_VERSION_MAJOR = params.BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    BUILD_VERSION_MINOR = params.BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y
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

    echo "Initializing build: #${currentBuild.number} - ${params.BUILD_VERSION}.??"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(DOOZER_WORKING)
    doozerOpts = "--working-dir ${DOOZER_WORKING} --group openshift-${params.BUILD_VERSION}"

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
                BUILD_MODE = "release"  // no other build mode remains relevant
            }

            stage("analyze") {

                dir(OSE_DIR) {
                    // inputs:
                    //  BUILD_VERSION

                    // defines
                    //  OSE_SOURCE_BRANCH
                    //  UPSTREAM_SOURCE_BRANCH
                    //  NEW_VERSION
                    //  NEW_RELEASE
                    //  NEW_DOCKERFILE_RELEASE
                    //  USE_WEB_CONSOLE_SERVER
                    //
                    //  sets:
                    //    currentBuild.displayName


                    OSE_SOURCE_BRANCH = "enterprise-${params.BUILD_VERSION}"
                    UPSTREAM_SOURCE_BRANCH = "upstream/release-${params.BUILD_VERSION}"
                    // Create the non-master source branch and have it track the origin ose repo
                    sh "git checkout -B ${OSE_SOURCE_BRANCH} origin/${OSE_SOURCE_BRANCH}"

                    echo "Building from ose branch: ${OSE_SOURCE_BRANCH}"

                    spec = buildlib.read_spec_info("origin.spec")
                    rel_fields = spec.release.tokenize(".")

                    if (! spec.version.startsWith("${params.BUILD_VERSION}.")) {
                        // Looks like pipeline thinks we are building something we aren't. Abort.
                        error("Expected version consistent with ${params.BUILD_VERSION}.* but found: ${spec.version}")
                    }


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

                    // decide which source to use for the web console
                    USE_WEB_CONSOLE_SERVER = false
                    if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR >= 9) {
                        USE_WEB_CONSOLE_SERVER = true
                    }

                    rpmOnlyTag = ""
                    if (!params.BUILD_CONTAINER_IMAGES) {
                        rpmOnlyTag = " (RPM ONLY)"
                    }
                    currentBuild.displayName = "#${currentBuild.number} - ${NEW_VERSION}-${NEW_RELEASE}${rpmOnlyTag}"
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
                    WEB_CONSOLE_BRANCH = "enterprise-${spec.major_minor}"
                    sh "git checkout -B ${WEB_CONSOLE_BRANCH} origin/${WEB_CONSOLE_BRANCH}"
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
                    WEB_CONSOLE_SERVER_BRANCH = "enterprise-${BUILD_VERSION_MAJOR}.${BUILD_VERSION_MINOR}"
                    dir(WEB_CONSOLE_SERVER_DIR) {
                        sh "git checkout ${WEB_CONSOLE_SERVER_BRANCH}"
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
                    // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                    if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                    } else {
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${params.BUILD_VERSION}"
                    }
                    sh "git checkout -B ${OPENSHIFT_ANSIBLE_SOURCE_BRANCH} origin/${OPENSHIFT_ANSIBLE_SOURCE_BRANCH}"
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
                    ${doozerOpts}
                    --source ose ${OSE_DIR}
                    rpms:build --version v${NEW_VERSION}
                    --release ${NEW_RELEASE}
                """
            }

            stage("plashet: ose 'building'") {
                if(params.DRY_RUN) {
                    echo "Running in dry-run mode -- will not run plashet."
                    return
                }

                def auto_signing_advisory = Integer.parseInt(buildlib.doozer("${doozerOpts} config:read-group --default=0 signing_advisory", [capture: true]).trim())

                buildlib.buildBuildingPlashet(NEW_VERSION, NEW_RELEASE, 7, true, auto_signing_advisory)  // build el7 embargoed plashet
                def plashet = buildlib.buildBuildingPlashet(NEW_VERSION, NEW_RELEASE, 7, false, auto_signing_advisory)  // build el7 unembargoed plashet
                PLASHET = plashet.plashetDirName
            }

            stage("update dist-git") {
                buildlib.doozer """
                    ${doozerOpts}
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
                            ${doozerOpts}
                            ${ODCS_FLAG}
                            ${exclude}
                            images:build
                            --filter-by-os amd64
                            --push-to-defaults ${ODCS_OPT}
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
            PLASHET = "v${NEW_FULL_VERSION}_${PLASHET}"
            final mirror_url = "https://mirror.openshift.com/enterprise/enterprise-${params.BUILD_VERSION}"

            stage("ami") {
                if (params.BUILD_AMI && params.BUILD_CONTAINER_IMAGES) {
                    // define openshift ansible source branch
                    OPENSHIFT_ANSIBLE_SOURCE_BRANCH = 'master'
                    // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                    if (BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6) {
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                    } else {
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${params.BUILD_VERSION}"
                    }
                    buildlib.build_ami(
                        BUILD_VERSION_MAJOR, BUILD_VERSION_MINOR,
                        NEW_VERSION, NEW_RELEASE,
                        "${mirror_url}/${PLASHET}/x86_64/os",
                        OPENSHIFT_ANSIBLE_SOURCE_BRANCH,
                        params.MAIL_LIST_FAILURE)
                }
            }

            buildlib.invoke_on_rcm_guest("publish-oc-binary.sh", params.BUILD_VERSION, NEW_FULL_VERSION)

            stage("sweep") {
                buildlib.sweep(params.BUILD_VERSION)
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
        buildlib.cleanWorkdir(DOOZER_WORKING)
    }
}
