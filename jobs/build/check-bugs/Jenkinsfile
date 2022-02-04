#!/usr/bin/env groovy
node {
    checkout scm
    buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib
    commonlib.describeJob("check-bugs", """
        ----------
        Check Bugs
        ----------
        Looks for blocker bugs and potential regressions, report findings on Slack.

        Timing: Daily run, scheduled.
    """)
}

pipeline {
    agent any

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        choice(
            name: "BUILD_VERSION",
            description: "OSE Version",
            choices
            : commonlib.ocpMajorVersions['all'],
        )
        string(
            name: "SLACK_CHANNEL",
            description: 'Slack channel to be notified in case of failures. ' +
                         'Example: #art-automation-debug ' +
                         'Leave blank to notify <strong>#art-release-{ocp-version}</strong>',
            defaultValue: '',
            trim: true,
        )
    }

    stages {
        stage("check-blockers") {
            steps {
                script {
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
                        """.stripIndent().tr("\n", " ").trim(),
                        returnStdout: true
                    ).trim()
                    echo "Found bugs: ${blocker_bugs}"

                    // If bugs found are > 0, notify Slack
                    num_bugs = blocker_bugs.split('\n').findAll{ it.startsWith( 'Found' ) }[0].split(' ')[1]

                    if (num_bugs.toInteger() > 0) {
                        echo "Found blocker bugs: sending Slack notification to ${slack_channel}"
                        commonlib.slacklib.to(slack_channel).say("""
                        *:warning: @release-artists - blocker bugs found for ${params.BUILD_VERSION}*
                        ```
                        ${blocker_bugs}
                        ```
                        """)
                    } else {
                        echo "No bugs found, skipping Slack spam"
                    }
                }
            }
        }
        stage("check-regressions") {
            steps {
                script {
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
                            returnStdout: true,
                            script: """
                                ${buildlib.ELLIOTT_BIN}
                                --group openshift-${params.BUILD_VERSION}
                                verify-bugs ${bugs}
                            """.stripIndent().tr("\n", " ").trim()
                        ).trim()
                        echo "No potential regressions found"
                    } catch (err) {
                        // There seems to be no way to capture stdout of a failing command
                        // see https://issues.jenkins.io/browse/JENKINS-64882
                        echo "Found potential regressions: sending Slack notification to ${slack_channel}"

                        // If regressions are found, notify Slack
                        commonlib.slacklib.to(slack_channel).say("""
                        *:warning: @release-artists - potential regressions for ${params.BUILD_VERSION}*
                        ```
                        There are potential regressions to look into:
                        Run this command for details:
                        ${buildlib.ELLIOTT_BIN} --group openshift-${params.BUILD_VERSION} verify-bugs ${bugs}
                        ```
                        """)
                    }
                }
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
