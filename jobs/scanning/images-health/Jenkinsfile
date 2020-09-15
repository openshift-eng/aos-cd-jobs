

node() {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    buildlib.kinit()

    properties(
        [
            disableConcurrentBuilds(),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    booleanParam(
                        name: 'SEND_TO_SLACK',
                        defaultValue: true,
                        description: "If false, output will only be sent to console"
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    def group = "openshift-${params.BUILD_VERSION}"
    def doozerOpts = "--working-dir ${doozer_working} --group ${group} "

    timestamps {

        slackChannel = slacklib.to(BUILD_VERSION)
        report = buildlib.doozer("${doozerOpts} images:health", [capture: true]).trim()
        if (report) {
            echo "The report:\n${report}"
            if (params.SEND_TO_SLACK) {
                slackChannel.say(":alert: Howdy, guys! There are some issues to look into for ${group}\n${report}")
            }
        } else {
            echo "There are no issues to report."
        }

    }
}


