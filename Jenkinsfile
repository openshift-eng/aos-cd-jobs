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
                            name: "NVRS",
                            description: "The list of image and RPM NVRS for which we need to kick off the scans for",
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
            if (!params.NVRS) {
                error("NVRS field should not be empty")
            }

            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"
        }

        stage("kick-off-scans") {
            def nvrs = params.NVRS.split(',')
            def cmd = []
            for (String nvr : nvrs) {
                if (nvr.contains("container")) {
                    cmd = [
                        "osh-cli",
                        "mock-build",
                        "--config=cspodman",
                        "--brew-build",
                        "${nvr}",
                        "--nowait"
                    ]
                } else {
                    def match = nvr =~ /(el[789])$/
                    def rhelVersion = ""

                    if (match) {
                        def endingPattern = match[0][1]
                        if (endingPattern == "el7") {
                            rhelVersion = "7"
                        } else if (endingPattern == "el8") {
                            rhelVersion = "8"
                        } else if (endingPattern == "el9") {
                            rhelVersion = "9"
                        } else {
                            error("Invalid RHEL version")
                        }
                    } else {
                        error("No regex match for RHEL version in RPM NVR: ${nvr}")
                    }

                    cmd = [
                        "osh-cli",
                        "mock-build",
                        "--config=rhel-${rhelVersion}-x86_64",
                        "--brew-build",
                        "${nvr}",
                        "--nowait"
                    ]
                }

                if (params.EMAIL) {
                        cmd << "--email-to ${EMAIL}"
                }

                echo "Will run ${cmd}"
                commonlib.shell(script: cmd.join(' '))
            }
        }
    }
}