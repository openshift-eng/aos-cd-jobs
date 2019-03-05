#!/usr/bin/env groovy

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
                    commonlib.ocpVersionParam('MINOR_VERSION', '4'),
                    [
                        name: 'VERSION_OVERRIDE',
                        description: 'Optional full version for build (e.g. v4.0.1). Defaults to atomic-openshift version',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ''
                    ],
                    [
                        name: 'RELEASE_OVERRIDE',
                        description: 'Optional release to use. By default, auto-increment previous build.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ''
                    ],
                    [
                        name: 'EXCLUSIONS',
                        description: 'Exclude these images from the scan. Comma or space separated list. (e.g. cri-o,openshift-enterprise-base)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'INCLUSIONS',
                        description: 'Only scan for specific images. Comma or space separated list. (e.g. cri-o,openshift-enterprise-base)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-team-art@redhat.com'
                    ],
                    [
                        name: 'ONLY_SCAN',
                        description: 'Only scan for changes, do not rebase and build',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    commonlib.mockParam(),
                ]
            ]
        ]
    )

    def mail_failure = { Map params ->
        def err = params.err ? params.err.getMessage() : "(unknown)"
        def subject = params.get("subject", "Problem with incremental build for ${params.MINOR_VERSION}")
        def stage = params.stage ? "in stage '${params.stage}' " : ""
        def extra_body = params.get("extra_body", "")
        commonlib.email(
                to: "${params.MAIL_LIST_FAILURE}",
                from: "aos-cicd@redhat.com",
                replyTo: 'aos-team-art@redhat.com',
                subject: subject,
                body: """\
Encountered an error ${stage}while running ${env.JOB_NAME}:
${err}

Jenkins job: ${env.BUILD_URL}
Console output: ${env.BUILD_URL}console

${extra_body}""")
    }

    buildlib.initialize()

    OSE_MAJOR = MINOR_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
    OSE_MINOR = MINOR_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y
    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}"

    EXCLUSIONS = commonlib.cleanCommaList(EXCLUSIONS)
    INCLUSIONS = commonlib.cleanCommaList(INCLUSIONS)
    def filter = INCLUSIONS ? "-i ${INCLUSIONS}" : "-i ''"
    if (EXCLUSIONS) {
        filter = "-x ${EXCLUSIONS}"
    }

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    // Clear out previous work
    sh "rm -rf ${DOOZER_WORKING}"
    sh "mkdir -p ${DOOZER_WORKING}"
    def doozer_opts = "--working-dir ${DOOZER_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}"

    List<String> images = []

    /* ************************************************************************** */
    currentBuild.description = "Scanning images"
    stage('Scan images') {

        try {
            def yamlData = readYaml text: buildlib.doozer(
                "${doozer_opts} ${filter} config:scan-sources --yaml", [capture: true]
            )
            // gotta parse out the list...
            yamlData["images"].each {
                if (it["changed"]) {
                   images.add(it["name"])
                }
            }
            if (!images) {
                currentBuild.description = "No images found to update."
                return
            }
            echo "Images that have changed:\n" + images.join("\n")

            def short_images = images.collect()
            if (images.size() > 2) {
                short_images = short_images[0..1]
                short_images.add("...")
            }
            currentBuild.description = "Changes to: " + short_images.join(", ")

            // also determine child images
            yamlData = readYaml text: buildlib.doozer(
                "${doozer_opts} images:show-tree --yml", [capture: true]
            )

            // scan the image tree for changed and their children using recursive closure
            Closure gather_children  // needs to be defined separately to self-call
            gather_children = { all, data, changed, gather ->
                // all(list): all images gathered so far while traversing tree
                // data(map): the part of the yaml image tree we're looking at
                // changed(list): all images initially found to have changed 
                // gather(bool): whether this is a subtree of an image with changed source
                data.each { image, children ->
                    def gather_this = gather || image in changed
                    if (gather_this) {  // this or an ancestor was a changed image
                        all.add(image)
                    }
                    // scan children recursively
                    all = gather_children(all, children, changed, gather_this)
                }
                return all
            }
            images = gather_children([], yamlData, images, false)
            echo "Total images to rebuild:\n" + images.join("\n")

        } catch (err) {

            currentBuild.description = "${err} during scan step"
            mail_failure(
                err: err,
                stage: "Scan images",
            )
            // Re-throw the error in order to fail the job
            throw err

        } finally {
            commonlib.safeArchiveArtifacts(["doozer_working/*.log"])
        }
    }

    if (ONLY_SCAN.toBoolean() || !images) {
        currentBuild.description += "\nNo images built."
        return
    }
    filter = "-i ${images.join(',')}"

    /* ************************************************************************** */
    stage('Rebase images') {

        try {
            sshagent(['openshift-bot']) {

                buildlib.kinit() // Sets up credentials for dist-git access

                // determine what version to use
                def version = VERSION_OVERRIDE.trim()
                def release = RELEASE_OVERRIDE.trim() ? RELEASE_OVERRIDE.trim() : "+"

                if (version == "") {
                    version = buildlib.doozer(
                        "${doozer_opts} --quiet images:query-rpm-version --repo-type unsigned",
                        [capture: true]
                    ).split(' ').last()
                } else {
                    version = version.startsWith("v") ? version : "v${version}"
                }

                echo "Images will be rebased and built at version-release ${version}-${release}"
                currentBuild.displayName = "#${currentBuild.number} - ${version}-${release}"

                // rebase all images with that version and release
                buildlib.doozer("""
                    ${doozer_opts} ${filter} --latest-parent-version
                    images:rebase
                    --push --version ${version} --release '${release}'
                    -m 'Rebuild on upstream change; version ${version}'
                """)
            }

        } catch (err) {

            currentBuild.description = "${err} during rebase step"
            mail_failure(
                err: err,
                stage: "Rebase images",
                extra_body: """Attempting to build updates for:\n${images.join("\n")}""",
            )
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            commonlib.safeArchiveArtifacts([
                "doozer_working/*.log",
                "doozer_working/*.yaml",
                "doozer_working/*.yml",
            ])
        }
    }

    /* ************************************************************************** */
    stage('Build images') {

        try {

            buildlib.kinit() // Sets up credentials for brew access

            buildlib.doozer """
                ${doozer_opts} ${filter}
                images:build
                --push-to-defaults --repo-type unsigned
            """

        } catch (err) {

            def failed_msg = ""

            echo "Error building images: ${err}"
            currentBuild.description = "${err} during build step"

            def record_log = buildlib.parse_record_log(DOOZER_WORKING)
            def failed_map = buildlib.get_failed_builds(record_log, true)
            if (failed_map) {
                // echo to console and description what happened
                def failed_msg = "The following build(s) failed:\n"
                failed_map.each { img, reason -> failed_msg += "${img}: ${reason} \n" }
                echo failed_msg
                currentBuild.description = failed_msg

                // send out emails to failed build owners
                def r = buildlib.determine_build_failure_ratio(record_log)
                if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
                    echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
                } else {
                    buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
                }
            }

            mail_failure(
                err: err,
                stage: "Build images",
                extra_body: failed_msg,
            )
            // Re-throw the error in order to fail the job
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

    // we probably don't want to spam email on success.
    // however a message to the UMB might be useful if anyone wants it.
}
