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
        releaseChannel = slacklib.to(BUILD_VERSION)
        try {
            withCredentials([string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN')]) {
                report = buildlib.doozer("${doozerOpts} images:streams prs list", [capture: true]).trim()
                if (report) {
                    data = readYaml text: report
                    text = ""
                    data.each { email, repos ->
                        text += "*${email} is a contact for these PRs:*\n"
                        repos.each { _, prs ->
                            prs.each { pr -> text += ":black_small_square:${pr.pr_url}\n" }
                        }
                    }
                    def attachment = [
                        color: "#f2c744",
                        blocks: [[type: "section", text: [type: "mrkdwn", text: text]]]
                    ]
                    releaseChannel.pinAttachment(attachment)
                    if (params.SEND_TO_SLACK) {
                        releaseChannel.say(":scroll: Howdy! Some alignment prs are still open for ${group}\n", [attachment])
                    }
                } else {
                    echo "There are no alignment prs left open."
                    if (params.SEND_TO_SLACK) {
                        releaseChannel.say(":scroll: All prs are merged for ${group}")
                    }
                }
            }
        } catch (exception) {
            releaseChannel.say(":alert: Image health check job failed!\n${BUILD_URL}")
            currentBuild.result = "FAILURE"
            throw exception  // gets us a stack trace FWIW
        }
    }
}
