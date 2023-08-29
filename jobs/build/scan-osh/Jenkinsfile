node('ocp-artifacts') {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("scan-osh", """
            <h2>Kick off SAST scans for builds</h2>
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
                        string(
                            name: "BUILD_NVRS",
                            description: "The list of builds for which we need to kick off the scan",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "RPM_NVRS",
                            description: "The list of builds for which we need to kick off the scan",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "EMAIL",
                            description: "Additional email to which the results of the scan should be sent out to",
                            defaultValue: "",
                            trim: true
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()

        stage("initialize") {
                if (!(params.BUILD_NVRS || params.RPM_NVRS)) {
                    error("Either BUILD_NVRS or RPM_NVRS is required")
                }
        }

        stage("images-scan") {
            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"

            if (params.BUILD_NVRS) {
                def builds = params.BUILD_NVRS.split(',')

                for (String build : builds) {
                    def cmd = [
                        "osh-cli",
                        "mock-build",
                        "--config=cspodman",
                        "--brew-build",
                        "${build}",
                        "--nowait"
                    ]

                    if (params.EMAIL) {
                        cmd << "--email-to ${EMAIL}"
                    }

                    echo "Will run ${cmd}"
                    commonlib.shell(script: cmd.join(' '))
                }
            }
        }

        stage("rpms-scan") {
            if (params.RPM_NVRS) {
                def rpms = params.RPM_NVRS.split(',')

                for (String rpm : rpms) {
                    def match = rpm =~ /(el[89])$/
                    def rhelVersion = ""

                    if (match) {
                        def endingPattern = match[0][1]
                        if (endingPattern == "el8") {
                            rhelVersion = "8"
                        } else if (endingPattern == "el9") {
                            rhelVersion = "9"
                        } else {
                            error("Invalid RHEL version")
                        }
                    } else {
                        error("No regex match for RHEL version in RPM NVR: ${rpm}")
                    }

                    def cmd = [
                        "osh-cli",
                        "mock-build",
                        "--config=rhel-${rhelVersion}-x86_64",
                        "--brew-build",
                        "${rpm}",
                        "--nowait"
                    ]

                    if (params.EMAIL) {
                        cmd << "--email-to ${EMAIL}"
                    }

                    echo "Will run ${cmd}"
                    commonlib.shell(script: cmd.join(' '))
                }
            }
        }
    }
}