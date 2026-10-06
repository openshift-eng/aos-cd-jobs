#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("force-new-nightly", """
        <h2>Force a new nightly payload</h2>
        <p>Triggers a new ART-managed nightly payload by poking the release
        controller imagestream. Supports both OCP and OKD.</p>
    """)

    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(logRotator(daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'VERSION',
                        description: 'The OCP/OKD minor version (e.g. 4.18, 5.1)',
                        trim: true,
                        defaultValue: ""
                    ),
                    choice(
                        name: 'PRODUCT',
                        description: 'Product variant',
                        choices: ['OCP', 'OKD'].join('\n'),
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    stage('Trigger nightly') {
        if (!params.VERSION) {
            error("You must provide a VERSION")
        }

        def ns
        def is
        if (params.PRODUCT == 'OKD') {
            ns = 'origin'
            is = "scos-${params.VERSION}-art"
        } else {
            ns = 'ocp'
            is = "${params.VERSION}-art-latest"
        }

        currentBuild.displayName = "${params.PRODUCT} ${params.VERSION}"

        buildlib.withAppCiAsArtPublish() {
            commonlib.shell(
                script: "oc tag --import-mode=PreserveOriginal --source=docker registry.access.redhat.com/ubi9 ${is}:trigger-release-controller -n ${ns}"
            )
            sleep 4
            commonlib.shell(
                script: "oc tag -d ${is}:trigger-release-controller -n ${ns}"
            )
        }
    }

    stage('Clean up') {
        buildlib.cleanWorkspace()
    }
    }
}
