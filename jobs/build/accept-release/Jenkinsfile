#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("accept-release", """
        <h2>Accept a release on Release Controller</h2>
    """)

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '7',
                    daysToKeepStr: '7'
                )
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'RELEASE_NAME',
                        description: 'Release name (e.g 4.10.4). Arch is amd64 by default.',
                        trim: true,
                        defaultValue: ""
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Release architecture (amd64, s390x, ppc64le, arm64)',
                        choices: ['amd64', 's390x', 'ppc64le', 'arm64'].join('\n'),
                    ),
                    string(
                        name: 'UPGRADE_URL',
                        description: 'URL to successful upgrade job',
                        trim: true,
                        defaultValue: ""
                    ),
                    string(
                        name: 'UPGRADE_MINOR_URL',
                        description: 'URL to successful upgrade-minor job',
                        trim: true,
                        defaultValue: ""
                    ),
                    booleanParam(
                        name: 'CONFIRM',
                        description: 'Running without this would be a [dry-run]. Must be specified to apply changes to server',
                        defaultValue: false
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    if (!params.RELEASE_NAME) {
        error("You must provide a release name")
    }
    if (!params.UPGRADE_URL) {
        error("You must provide a URL to successful upgrade job")
    }
    if (!params.UPGRADE_MINOR_URL) {
        error("You must provide a URL to successful upgrade-minor job")
    }

    def dry_run = params.CONFIRM ? '' : '[DRY_RUN]'
    currentBuild.displayName = "${params.RELEASE_NAME} ${dry_run}"

    def confirm_param = params.CONFIRM ? "--confirm" : ''

    buildlib.withAppCiAsArtPublish() {
        commonlib.shell(
            script: """
                hacks/release_controller/accept.py \
                  --release ${params.RELEASE_NAME} \
                  --arch ${params.ARCH} \
                  --upgrade-url ${params.UPGRADE_URL} \
                  --upgrade-minor-url ${params.UPGRADE_MINOR_URL} \
                  ${confirm_param}
                """,
        )
    }
    buildlib.cleanWorkspace()
}
