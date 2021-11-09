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
            choices: commonlib.ocpMajorVersions['all'],
        )
    }

    stages {
        stage("check-blockers") {
            steps {
                script {
                    blocker_bugs = commonlib.shell(
                        returnStdout: true,
                        script: """
                            ${buildlib.ELLIOTT_BIN}
                            --group openshift-${params.BUILD_VERSION}
                            find-bugs
                            --mode blocker
                            --report
                        """.stripIndent().tr("\n", " ").trim()
                    ).trim()
                }
            }
        }
        stage("check-regressions") {
            steps {
                script {
                    if (next_is_prerelease(params.BUILD_VERSION)) {
                        return
                    }
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

                    potential_regressions = commonlib.shell(
                        returnStdout: true,
                        script: """
                            ${buildlib.ELLIOTT_BIN}
                            --group openshift-${params.BUILD_VERSION}
                            verify-bugs ${bugs}
                        """.stripIndent().tr("\n", " ").trim()
                    ).trim()
                }
            }
        }
        stage("slack-notification") {
            steps {
                script {
                    commonlib.slacklib.to(params.BUILD_VERSION).say("""
                    *blocker bugs*
                    ```
                    ${blocker_bugs}
                    ```

                    *potential regressions*
                    ```
                    ${potential_regressions}
                    ```
                    """)
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
