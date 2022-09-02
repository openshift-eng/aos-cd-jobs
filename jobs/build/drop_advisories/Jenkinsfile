#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("drop_advisories", """
        <h2>Runs elliott drop-advisory command for one or more advisories</h2>
    """)

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '7',
                    daysToKeepStr: '7'
                )
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('VERSION', '4'),
                    string(
                        name: 'ADVISORIES',
                        description: 'One or more advisories to drop, comma separated',
                        trim: true
                    ),
                    string(
                        name: 'COMMENT',
                        description: 'The comment will add to the bug attached on the advisory to explain the reason, if not set will use default comment',
                        defaultValue: "This bug will be dropped from current advisory because the advisory will also be dropped and not going to be shipped.",
                        trim: true
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    if (!params.ADVISORIES) {
        error("You must provide one or more advisories.")
    }

    advisory_list = commonlib.parseList(params.ADVISORIES)

    for(adv in advisory_list) {
        def elliott = "${buildlib.ELLIOTT_BIN} --group=openshift-${params.VERSION}"
        withCredentials([string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
            commonlib.shell(
                script: """
                ${elliott} repair-bugs --advisory ${adv} --auto --comment "${comment}" --close-placeholder --from RELEASE_PENDING --to VERIFIED
                ${elliott} remove-bugs --advisory ${adv} --all
                ${elliott} change-state --state NEW_FILES --advisory ${adv}
                ${elliott} advisory-drop ${adv}
                """,
            )
        }
    }

    buildlib.cleanWorkspace()
}
