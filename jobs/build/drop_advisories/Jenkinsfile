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
        res = commonlib.shell(
            returnAll: true,
            script: """
              ${buildlib.ELLIOTT_BIN} repair-bugs --advisory ${adv} --all --comment "${comment}" --close-placeholder --from RELEASE_PENDING --to VERIFIED
              ${buildlib.ELLIOTT_BIN} remove-bugs --advisory ${adv} --all
              ${buildlib.ELLIOTT_BIN} change-state --state NEW_FILES --advisory ${adv}
              ${buildlib.ELLIOTT_BIN} advisory-drop ${adv}
            """,
        )
        print(res)
    }

    buildlib.cleanWorkspace()
}
