#!/usr/bin/env groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib

    commonlib.describeJob("check-bugs", """
        ----------
        Check Bugs
        ----------
        Looks for blocker bugs and potential regressions, report findings on Slack.

        Timing: Daily run, scheduled.
    """)

    properties(
        [
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    choice(
                        name: "BUILD_VERSION",
                        description: "OSE Version",
                        choices: commonlib.ocpMajorVersions['all'],
                    ),
                    string(
                        name: "SLACK_CHANNEL",
                        description: 'Slack channel to be notified in case of failures. ' +
                                    'Example: #art-automation-debug ' +
                                    'Leave blank to notify <strong>#art-release-{ocp-version}</strong>',
                        defaultValue: '',
                        trim: true,
                    ),
                    booleanParam(
                        name: "NOTIFY_FORUM_RELEASE",
                        description: "Notify #forum-release about blockers and regressions",
                        defaultValue: false,
                    )
                ]
            ]
        ]
    )

    // Check for mock build
    commonlib.checkMock()

    // Set build name to OCP version
    currentBuild.displayName = params.BUILD_VERSION

    // Check pre-release state, except for 3.11
    if ( (params.BUILD_VERSION != "3.11") && (! is_ga(params.BUILD_VERSION)) ) {
        error("version ${params.BUILD_VERSION} is in pre-release state: skipping job")
    }

    stage("check-blockers") {
        // Check Slack channel to notify
        slack_channel = params.SLACK_CHANNEL ? params.SLACK_CHANNEL : params.BUILD_VERSION

        // Find blocker bugs
        blocker_bugs = sh(
            script: """
                ${buildlib.ELLIOTT_BIN}
                --group openshift-${params.BUILD_VERSION}
                find-bugs
                --mode blocker
                --report
                --output slack
            """.stripIndent().tr("\n", " ").trim(),
            returnStdout: true
        ).trim()

        // If bugs found are > 0, notify Slack
        if (blocker_bugs == "") {
            echo "No bugs found"
        } else {
            num_bugs = sh(
                script: """
                    echo "${blocker_bugs}" | wc -l
                """,
                returnStdout: true
            )
            echo "Found ${num_bugs} bugs: sending Slack notification to ${slack_channel}"
            echo "${blocker_bugs}"

            message = """
            *:warning: @release-artists - blocker bugs found for ${params.BUILD_VERSION}*
            ${blocker_bugs}
            """

            commonlib.slacklib.to(slack_channel).say(message)
            if (params.NOTIFY_FORUM_RELEASE) {
                commonlib.slacklib.to("#forum-release").say(message)
            }
        }
    }

    stage("check-regressions") {
        // Do not run for 3.11
        if (params.BUILD_VERSION == "3.11") {
            echo "Skipping regression checks for 3.11"
            return
        }

        // Check pre-release
        if (next_is_prerelease(params.BUILD_VERSION)) {
            echo "No pre-release: skipping regressions"
            return
        }

        // Find bugs
        bugs = commonlib.shell(
            returnStdout: true,
            script: """
                ${buildlib.ELLIOTT_BIN}
                --group openshift-${params.BUILD_VERSION}
                find-bugs
                --mode sweep
                | tail -n1
                | cut -d':' -f2
                | tr -d ,
            """.stripIndent().tr("\n", " ").trim()
        ).trim()
        echo "Found bugs: ${bugs}"

        // Verify bugs
        // elliott verify-bugs will exit with 1
        // in case potential regressions are found
        def potential_regressions = ""
        try {
            potential_regressions = commonlib.shell(
                script: """
                    ${buildlib.ELLIOTT_BIN}
                    --group openshift-${params.BUILD_VERSION}
                    verify-bugs ${bugs}
                    > .log
                """.stripIndent().tr("\n", " ").trim()
            ).trim()
            echo "No potential regressions found"
        } catch (err) {
            // If regressions are found, notify Slack
            echo "Found potential regressions: sending Slack notification to ${slack_channel}"
            potential_regressions = sh(
                script: """
                    cat .log
                """,
                returnStdout: true
            )

            message = """
            *:warning: Hi @release-artists, there are potential regressions to look into for ${params.BUILD_VERSION}*
            ```
            ${potential_regressions}
            ```
            """

            commonlib.slacklib.to(slack_channel).say(message)
            if (params.NOTIFY_FORUM_RELEASE) {
                commonlib.slacklib.to("#forum-release").say(message)
            }
        }
    }
}

def next_is_prerelease(version) {
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(version)
    def next_version = major.toString() + '.' + (minor + 1).toString()
    try {
        return commonlib.ocpReleaseState[next_version]['release'].isEmpty()
    } catch (Exception e) {
        // there is no "next_version" release defined in ocpReleaseState
        return true
    }
}

def is_ga(version) {
    command = "curl  -sH 'Accept: application/json' " +
              "'https://api.openshift.com/api/upgrades_info/v1/graph?arch=amd64&channel=fast-${version}' | " +
              "jq .nodes | jq length"

    echo "Executing command: '${command}'"
    length = sh(
        returnStdout: true,
        script: command
    )
    
    return length.toInteger() > 0
}