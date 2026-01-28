#!/usr/bin/env groovy
node {
    timestamps {
    checkout scm
    def commonlib = load("pipeline-scripts/commonlib.groovy")

    commonlib.describeJob("check-disk-usage-on-buildvm", """
----------
Check disk usage on buildvm
----------
Check if disk usage on buildvm exceeds a treshold;
notify ART team if it does.
    """)


    properties(
        [
            disableResume(),
            buildDiscarder(logRotator(daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    string(
                        name: "THRESHOLD",
                        description: 'Max disk usage, expressed as percentage; example: 90',
                        defaultValue: '90',
                        trim: true,
                    ),
                    string(
                        name: "SLACK_CHANNEL",
                        description: 'Slack channel to notify. ' +
                                     'Example: #team-art-debug',
                        defaultValue: '#team-art',
                        trim: true,
                    )
                ]
            ]
        ]
    )

    // Check for mock build
    commonlib.checkMock()

    def partitions_to_check = [
        "/mnt/jenkins-home",
        "/mnt/jenkins-workspace",
    ]

    warnings = []
    for (String partition : partitions_to_check) {

        def result = sh(
            script: """
                set +e
                df -P ${partition} 2>/dev/null | awk 'NR==2 { sub("%","",$5); print $5 }'
            """,
            returnStdout: true
        ).trim()

        if (!result.isInteger()) {
            echo "Warning: Could not determine disk usage for ${partition}. Output: '${result}'"
            continue
        }

        def disk_usage = result.toInteger()

        echo "Disk usage on '${partition}': ${disk_usage}%"

        if (disk_usage > params.THRESHOLD.toInteger()) {
            warnings.add("Disk usage on \u0060${partition}\u0060: ${disk_usage}%")
        }
    }

    if (warnings) {
        message = "*:warning: @release-artists buildvm disk usage alert*"
        for (String warning : warnings) {
            message = message + "\n" + warning
        }
        echo message
        commonlib.slacklib.to(params.SLACK_CHANNEL).say(message)
    } else {
        echo "No disk space warnings"
    }
    }
}
