node("ocp-artifacts") {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("scan-osh", """
            <h2>Kick off SAST scans for builds in candidate tags for a particular version</h2>
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "30",
                        artifactNumToKeepStr: "",
                        daysToKeepStr: "30",
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.dryrunParam(),
                        commonlib.mockParam(),
                        commonlib.artToolsParam(),
                        string(
                            name: "NVRS",
                            description: "The list of image and RPM NVRS for which we need to kick off the scans for",
                            defaultValue: "",
                            trim: true
                        ),
                        commonlib.ocpVersionParam("BUILD_VERSION", "4"),
                        booleanParam(
                            name: "CHECK_TRIGGERED",
                            description: "Kick off scans for NVRs that haven't been triggered for. Can be used alongside ALL_BUILDS and NVRS param",
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: "ALL_BUILDS",
                            description: "Trigger scans for all builds in all candidate tags. Cannot be used if NVRS param is set",
                            defaultValue: false,
                        ),
                    ]
                ],
            ]
        )

        commonlib.checkMock()

        stage("initialize") {
            if (params.NVRS && params.ALL_BUILDS) {
                error("Both NVRS and ALL_BUILDS value can't be set")
            }

            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"
        }

        stage("kick-off-scans") {
            def cmd = [
                    "artcd",
                    "-vv",
                    "--working-dir=./artcd_working",
                    "--config=./config/artcd.toml",
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }

            cmd += [
                "scan-osh",
                "--version=${params.BUILD_VERSION}",
            ]

            if (params.NVRS) {
                cmd << "--nvrs ${params.NVRS}"
            } else {
                if (params.ALL_BUILDS) {
                    cmd << "--all-builds"
                }
            }
            if (params.CHECK_TRIGGERED) {
                    cmd << "--check-triggered"
            }

            withCredentials([
                        string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                        string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                        string(credentialsId: 'redis-port', variable: 'REDIS_PORT'),
             ]) {
                echo "Will run ${cmd}"
                commonlib.shell(script: cmd.join(" "))

            }
        }
    }
}