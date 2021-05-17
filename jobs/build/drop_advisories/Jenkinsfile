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
            script: "${buildlib.ELLIOTT_BIN} advisory-drop ${adv}",
        )
        print(res)
    }
        
    buildlib.cleanWorkspace()
}
