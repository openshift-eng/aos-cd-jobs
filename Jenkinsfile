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
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'RELEASE_NAME',
                        description: 'Release name (e.g 4.10.4 or nightly). Arch is amd64 by default.',
                        trim: true,
                        defaultValue: ""
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Release architecture (amd64, s390x, ppc64le, arm64, multi)',
                        choices: ['amd64', 's390x', 'ppc64le', 'arm64', 'multi'].join('\n'),
                    ),
                    booleanParam(
                        name: 'REJECT',
                        description: 'Instead of Accepting, Reject a release',
                        defaultValue: false
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

    stage('Accept release') {
        if (!params.RELEASE_NAME) {
            error("You must provide a release name")
        }

        def dry_run = params.CONFIRM ? '' : '[DRY_RUN]'
        currentBuild.displayName = "${params.RELEASE_NAME} ${dry_run}"

        def action = params.REJECT ? "reject" : 'accept'
        def message = "Manually ${action}ed by ART"
        def confirm_param = params.CONFIRM ? "--execute" : ''

        script {
            sh "wget https://raw.githubusercontent.com/openshift/release-controller/master/hack/release-tool.py"
            buildlib.withAppCiAsArtPublish() {
                commonlib.shell(
                    script: """
                        if [[ -f /bin/scl ]]; then
                        scl enable rh-python38 -- python3 release-tool.py --message "${message}" --reason "${message}" --architecture ${params.ARCH} -c `oc config current-context` ${confirm_param} ${action} ${params.RELEASE_NAME}
                        else
                        python3 release-tool.py --message "${message}" --reason "${message}" --architecture ${params.ARCH} -c `oc config current-context` ${confirm_param} ${action} ${params.RELEASE_NAME}
                        fi
                        """,
                )
            }
        }
    }

    stage('Clean up') {
        buildlib.cleanWorkspace()
    }
}
