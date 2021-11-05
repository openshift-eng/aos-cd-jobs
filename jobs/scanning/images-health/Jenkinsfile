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
                    choice(
                        name: 'ALERT_DATE', 
                        choices: [
                            'Monday',
                            'Tuesday',
                            'Wednesday', 
                            'Thursday',
                            'Friday'
                        ].join('\n'), 
                        description: 'In which day check upstream prs'
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

        try {
            report = buildlib.doozer("${doozerOpts} images:health", [capture: true]).trim()
            if (report) {
                echo "The report:\n${report}"
                if (params.SEND_TO_SLACK) {
                    slackChannel.say(":alert: Howdy! There are some issues to look into for ${group}\n${report}")
                }
            } else {
                echo "There are no issues to report."
                if (params.SEND_TO_SLACK) {
                    slackChannel.say(":heavy_check_mark: All images are healthy for ${group}")
                }
            }
        } catch (exception) {
            slackChannel.say(":alert: Image health check job failed!\n${BUILD_URL}")
            currentBuild.result = "FAILURE"
            throw exception  // gets us a stack trace FWIW
        }
        
        def week = [1:'Sunday', 2:'Monday', 3:'Tuesday', 4:'Wednesday', 5:'Thursday', 6:'Friday', 7:'Saturday']
        Date today = new Date();
        Calendar c = Calendar.getInstance();
        c.setTime(today);
        if ( week[c.get(Calendar.DAY_OF_WEEK)] == params.ALERT_DATE ) {  // to avoid spam message only check once on Mon
            withCredentials([string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN')]) {
                slackChannel = slacklib.to(BUILD_VERSION)
                try {
                    report = buildlib.doozer("${doozerOpts} images:streams prs list", [capture: true]).trim()
                    if (report) {
                        data = readYaml text: report
                        text = ""
                        data.each { email, repo ->
                            text += "*${email} is a contact for these PRs:*\n"
                            repos.each { repo, prs ->
                                prs.each { pr -> text += ":black_small_square:${pr.pr_url}\n" }
                            }
                        }
                        def attachment = [
                            color: "#f2c744",
                            blocks: [[type: "section", text: [type: "mrkdwn", text: text]]]
                        ]
                        slackChannel.pinAttachment(attachments)
                        if (params.SEND_TO_SLACK) {
                            slackChannel.say(":scroll: Howdy! Some alignment prs are still open for ${group}\n", [attachment])
                        }
                    } else {
                        echo "There are no alignment prs left open."
                        if (params.SEND_TO_SLACK) {
                            slackChannel.say(":scroll: All prs are merged for ${group}")
                        }
                    }
                } catch (exception) {
                    slackChannel.say(":alert: Image health check job failed!\n${BUILD_URL}")
                    currentBuild.result = "FAILURE"
                    throw exception  // gets us a stack trace FWIW
                }
            }
        }
    }
}
