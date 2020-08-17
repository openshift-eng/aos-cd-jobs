#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def quay_url = "quay.io/openshift-release-dev/ocp-release-nightly"
    commonlib.describeJob("pre-release", """
        -------------------------------------------------
        Publish accepted nightlies as public pre-releases
        -------------------------------------------------
        Timing: Usually run by the poll-payload scheduled job whenever there is
        a new accepted pre-GA build that needs to be published.
        Nightlies are not published once Release Candidates are building.

        This job clones the release image to the public release quay repo
            quay.io/openshift-release-dev/ocp-release-nightly
        and publishes clients for it to 
            http://mirror.openshift.com/pub/openshift-v4/<arch>/clients/ocp-dev-preview/
    """)


    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    choice(
                        name: 'ARCH',
                        description: 'The architecture for this release',
                        choices: [
                            "x86_64",
                            "s390x",
                            "ppc64le",
                        ].join("\n"),
                    ),
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Optional. If not specified, an attempt will be made to detect the latest nightly. e.g. 4.1.0-0.nightly-2019-04-22-005054',
                        defaultValue: ""
                    ),
                    string(
                        name: 'NEW_NAME_OVERRIDE',
                        description: 'Release name (if not specified, uses detected name or FROM_RELEASE_TAG)',
                        defaultValue: ""
                    ),
                    booleanParam(
                        name: 'PERMIT_PAYLOAD_OVERWRITE',
                        description: 'Allows the pipeline to overwrite an existing payload in quay. Use only to recover from a pre-release that failed at client sync.',
                        defaultValue: false
                    ),
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Only do dry run test and exit.',
                        defaultValue: false
                    ),
                    booleanParam(
                        name: 'MIRROR',
                        description: 'Sync clients to mirror.',
                        defaultValue: true
                    ),
                    booleanParam(
                        name: 'SET_CLIENT_LATEST',
                        description: 'Set latest links for client.',
                        defaultValue: true
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                    commonlib.suppressEmailParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    try {
        sshagent(['aos-cd-test']) {

            def from_release_tag = params.FROM_RELEASE_TAG.trim()

            if ( from_release_tag == "" ) {
                // If no name was specified, interrogate the stream
                def releaseStream = "${params.BUILD_VERSION}.0-0.nightly"
                if ( params.ARCH != 'x86_64' ) {
                    releaseStream += "-${params.ARCH}"
                }
                // There are different release controllers for OCP - one for each architecture.
                RELEASE_CONTROLLER_URL = commonlib.getReleaseControllerURL(releaseStream)

                // Search for the latest version in this X.Y, but less than X.Y+1
                def queryEndpoint = "${RELEASE_CONTROLLER_URL}/api/v1/releasestream/${releaseStream}/latest"
                from_release_tag = commonlib.shell(
                    returnStdout: true,
                    script: "curl -L --fail -s -X GET -G ${queryEndpoint} | jq '.name' -r"
                ).trim()
                echo "Detected latest release in ${params.BUILD_VERSION}: ${from_release_tag}"
            }

            currentBuild.displayName = "#${currentBuild.number} - ${from_release_tag}"
            if (params.DRY_RUN) { currentBuild.displayName += " [dry run]"}
            if (!params.MIRROR) { currentBuild.displayName += " [no mirror]"}

            if (!from_release_tag.startsWith(params.BUILD_VERSION)) {
                error("The source release tag ${from_release_tag} does not start with the ${params.BUILD_VERSION}")
            }

            def (arch, priv) = release.getReleaseTagArchPriv(from_release_tag)
            if (priv) {
                error("The source release tag ${from_release_tag} is an embargoed nightly. It shouldn't be pre-released.")
            }

            def dest_release_tag = from_release_tag
            if ( params.NEW_NAME_OVERRIDE.trim() != "" ) {
                dest_release_tag = params.NEW_NAME_OVERRIDE.trim()
            }

            stage("versions") { release.stageVersions() }

            buildlib.registry_quay_dev_login()

            def CLIENT_TYPE = "ocp-dev-preview"

            stage("validation") {
                release.stageValidation(quay_url, dest_release_tag, -1, params.PERMIT_PAYLOAD_OVERWRITE)
            }

            stage("build payload") {
                release.stageGenPayload(quay_url, dest_release_tag, dest_release_tag, from_release_tag, "", "", "")
            }

            stage("mirror tools") {
                if ( params.MIRROR ) {
                    release.stagePublishClient(quay_url, dest_release_tag, dest_release_tag, arch, CLIENT_TYPE)
                }
            }

            stage("sign") {
                if ( params.MIRROR ) {
                    release.signArtifacts(
			name: dest_release_tag,
			signature_name: "signature-1",
			dry_run: params.DRY_RUN,
			env: "prod",
			key_name: "beta2",
			arch: arch,
			digest: payloadDigest,
			client_type: 'ocp-dev-preview',
		    )
                }
            }

            stage("set client latest") {
                if ( params.MIRROR && params.SET_CLIENT_LATEST ) {
                    release.stageSetClientLatest(dest_release_tag, arch, CLIENT_TYPE)
                }
            }

        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Pre-Release",
            body: "Encountered an error while running OCP pre release: ${err}");
        currentBuild.description = "Error while running OCP pre release:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}
