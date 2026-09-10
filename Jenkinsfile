#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("rhcos-node-image-post-build", """
        <h2>Run RHCOS node image integration tests and promote tested images</h2>
        <p>This job accepts immutable RHCOS image pullspecs and can be replayed
        with Jenkins Rebuild without resolving new image records.</p>
    """)

    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.artToolsParam(),
                    commonlib.dryrunParam(),
                    string(
                        name: 'RELEASE',
                        description: 'RHCOS release stream, for example 5.0-9.8',
                        defaultValue: '',
                        trim: true,
                    ),
                    string(
                        name: 'NODE_IMAGE',
                        description: 'Immutable RHCOS node image pullspec',
                        defaultValue: '',
                        trim: true,
                    ),
                    string(
                        name: 'EXTENSIONS_IMAGE',
                        description: 'Immutable RHCOS extensions image pullspec',
                        defaultValue: '',
                        trim: true,
                    ),
                ],
            ],
        ]
    )

    commonlib.checkMock()

    stage("Validate parameters") {
        if (!params.RELEASE || !params.NODE_IMAGE || !params.EXTENSIONS_IMAGE) {
            error("RELEASE, NODE_IMAGE, and EXTENSIONS_IMAGE must be specified")
        }
    }

    try {
        stage("RHCOS post-build") {
            buildlib.setup_venv()
            buildlib.init_artcd_working_dir()

            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
            ]
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "rhcos-node-image-post-build",
                "--release=${params.RELEASE}",
                "--node-image=${params.NODE_IMAGE}",
                "--extensions-image=${params.EXTENSIONS_IMAGE}",
            ]

            withCredentials([
                file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                file(credentialsId: 'art-rhcos-images-sa', variable: 'RHCOS_QUAY_AUTH_FILE'),
                file(credentialsId: 'rhcos--prod-pipeline_jenkins_api-prod-stable-spoke1-dc-iad2-itup-redhat-com', variable: 'RHCOS_JENKINS_KUBECONFIG'),
            ]) {
                echo "Will run ${cmd.join(' ')}"
                commonlib.shell(script: cmd.join(' '))
            }
        }
    } finally {
        commonlib.safeArchiveArtifacts([
            "artcd_working/**/*.log",
        ])
        buildlib.cleanWorkspace()
    }
    }
}
