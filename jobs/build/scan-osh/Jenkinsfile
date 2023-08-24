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
                if (!params.BUILD_NVRS) {
                    error("BUILD_NVRS is required")
                }
        }

        stage("kick-off-scan") {
            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"

            def builds = BUILD_NVRS.split(',')

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
}