#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("sync-rhcos-bfb", """
        <h2>Sync RHCOS NVIDIA BFB artifacts to mirror</h2>
        <p>
        Syncs RHCOS NVIDIA .bfb artifacts from the internal RHCOS s3 bucket to mirror.openshift.com.
        </p>
        <p>
        <strong>The pipeline copies BFB artifacts to two locations:</strong><br/>
        • <code>/pub/openshift-v4/aarch64/dependencies/nvidia-bfb/pre-release/{major.minor}-latest/</code><br/>
        • <code>/pub/openshift-v4/aarch64/dependencies/nvidia-bfb/pre-release/{major.minor}-{build}/</code>
        </p>
    """)

    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30',
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                    commonlib.artToolsParam(),
                    string(
                        name: "STREAM",
                        description: "RHCOS stream identifier (e.g., '4.20-9.6-nvidia-bfb')",
                        defaultValue: "",
                        trim: true
                    ),
                    string(
                        name: "BUILD",
                        description: "RHCOS build identifier (e.g., '9.6.20250707-1.3')",
                        defaultValue: "",
                        trim: true
                    ),
                ],
            ]
        ]
    )

    commonlib.checkMock()

    stage("Validate parameters") {
        if (!params.STREAM) {
            error("STREAM must be specified")
        }

        if (!params.BUILD) {
            error("BUILD must be specified")
        }

        echo("Initializing RHCOS BFB sync: stream=${params.STREAM}, build=${params.BUILD}")
    }

    stage("Sync RHCOS BFB") {
        def cmd = [
            "artcd",
            "-vv",
            "--config=./config/artcd.toml",
            "--working-dir=./artcd_working",
        ]

        if (params.DRY_RUN) {
            cmd << "--dry-run"
        }

        cmd += [
            "sync-rhcos-bfb",
            "--type=bfb",
            "--stream", params.STREAM,
            "--build", params.BUILD,
        ]

        withCredentials([
            file(credentialsId: 'aws-credentials-file', variable: 'AWS_SHARED_CREDENTIALS_FILE'),
            string(credentialsId: 's3-art-srv-enterprise-cloudflare-endpoint', variable: 'CLOUDFLARE_ENDPOINT')
        ]) {
            buildlib.init_artcd_working_dir()
            echo "Will run ${cmd}"
            commonlib.shell(script: cmd.join(' '))
        }
    }

    buildlib.cleanWorkspace()
}
