#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("oc_sync", """
        <h2>Sync the oc, installer, and opm clients to mirror</h2>
        Extracts the clients from the payload cli-artifacts and operator-registry images and publishes them to
        <a href="http://mirror.openshift.com/pub/openshift-v4/clients/ocp" target="_blank">the mirror</a>
        or <a href="http://mirror.openshift.com/pub/openshift-v4/clients/ocp-dev-preview" target="_blank">ocp-dev-preview</a>

        <b>Timing</b>: This is only ever run by humans, typically when the release job
        fails somehow. Normally the release job syncs these clients itself.
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
                    string(
                        name: 'RELEASE_NAME',
                        description: 'e.g. 4.2.6 or 4.3.0-0.nightly-2019-11-13-233341',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'architecture being synced',
                        choices: commonlib.brewArches.join('\n'),
                    ),
                    choice(
                        name: 'CLIENT_TYPE',
                        description: 'artifacts path under https://mirror.openshift.com',
                        choices: [
                            "ocp",
                            "ocp-dev-preview",
                        ].join("\n"),
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-oc-sync@redhat.com'
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.dryrunParam('Take no actions.'),
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()

    def ocpVersion = commonlib.extractMajorMinorVersion(params.RELEASE_NAME)

    try {
        currentBuild.displayName = "#${currentBuild.number} - ${params.RELEASE_NAME} - ${params.CLIENT_TYPE}"

        def arch = params.ARCH
        def releaseTag = release.destReleaseTag(params.RELEASE_NAME, arch)

        if (params.CLIENT_TYPE == 'ocp') {
            if (params.RELEASE_NAME.contains('nightly')) {
                error("I'm not sure you want to publish a nightly out as the ocp client type")
            }
            pull_spec = "quay.io/openshift-release-dev/ocp-release:${releaseTag}"
        } else if (params.CLIENT_TYPE == 'ocp-dev-preview') {
            pull_spec = "quay.io/openshift-release-dev/ocp-release-nightly:${releaseTag}"
        } else {
            error("CLIENT_TYPE ${params.CLIENT_TYPE} is unknown.")
        }

        sshagent(['aos-cd-test']) {
            stage("sync ocp clients") {
                // must be able to access remote registry to extract image contents
                buildlib.registry_quay_dev_login()
                timeout(time: 60, unit: 'MINUTES') {
                    withEnv(["DRY_RUN=${params.DRY_RUN? '1' : ''}"]){
                        commonlib.shell "./publish-clients-from-payload.sh ${env.WORKSPACE} ${params.RELEASE_NAME} ${params.CLIENT_TYPE} '${pull_spec}'"
                    }
                }
                if (!params.DRY_RUN) {
                    slacklib.to(ocpVersion).say("""
                    *:heavy_check_mark: oc_sync successful*
                    https://mirror.openshift.com/pub/openshift-v4/${params.ARCH}/clients/${params.CLIENT_TYPE}/${params.RELEASE_NAME}/

                    buildvm job: ${commonlib.buildURL('console')}
                    """)
                }
            }
        }
    } catch (err) {
        def buildURL = env.BUILD_URL.replace('https://buildvm.openshift.eng.bos.redhat.com:8443', 'https://localhost:8888')
        if (!params.DRY_RUN) {
            slacklib.to(ocpVersion).say("""
            *:heavy_exclamation_mark: oc_sync failed*
            buildvm job: ${commonlib.buildURL('console')}
            """)
        }
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "${params.DRY_RUN? '[DRY RUN]' : ''}Error syncing ocp client from payload",
            body: """Encountered an error while syncing ocp client from payload: ${err}

Jenkins Job: ${buildURL}

""");
        currentBuild.description = "Error while syncing ocp client from payload:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
    buildlib.cleanWorkdir(env.WORKSPACE)  // at end of job, ok to wipe out code
    buildlib.cleanWorkspace()
}
