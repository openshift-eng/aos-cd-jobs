#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = buildlib.commonlib
    commonlib.describeJob("oc_sync", """
        -------------------------------------------
        Sync the oc and installer clients to mirror
        -------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/ocp (or ocp-dev-preview)
        Extracts the clients from the payload cli-artifacts image and publishes them.

        Timing: This is only ever run by humans, typically when the release job
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
                        defaultValue: ""
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'architecture being synced',
                        choices: ['x86_64', 's390x', 'ppc64le'].join('\n'),
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
                        ].join(',')
                    ),
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()



    try {
        currentBuild.displayName = "#${currentBuild.number} - ${params.RELEASE_NAME} - ${params.CLIENT_TYPE}"

        def arch = params.ARCH
        def releaseTag = release.destReleaseTag(params.RELEASE_NAME, arch)

        if (params.CLIENT_TYPE == 'ocp') {
            if (params.RELEASE_NAME.contains('nightly')) {
                error("I'm not sure you want to publish a nightly out as the ocp client type")
            }
            pull_spec = "quay.io/openshift-release-dev/ocp-release:${releaseTag}"
        } else {
            pull_spec = "quay.io/openshift-release-dev/ocp-release-nightly:${releaseTag}"
        }

        sshagent(['aos-cd-test']) {
            stage("sync ocp clients") {
                // must be able to access remote registry to extract image contents
                buildlib.registry_quay_dev_login()
                commonlib.shell "./publish-clients-from-payload.sh ${env.WORKSPACE} ${params.RELEASE_NAME} ${params.CLIENT_TYPE} '${pull_spec}'"
            }
        }
    } catch (err) {
        def buildURL = env.BUILD_URL.replace('https://buildvm.openshift.eng.bos.redhat.com:8443', 'https://localhost:8888')
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error syncing ocp client from payload",
            body: """Encountered an error while syncing ocp client from payload: ${err}

Jenkins Job: ${buildURL}

""");
        currentBuild.description = "Error while syncing ocp client from payload:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
    buildlib.cleanWorkdir("${env.WORKSPACE}")
}
