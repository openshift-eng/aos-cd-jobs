#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("multi_promote", """
        <h2>Kick off multiple promote jobs for selected nightlies</h2>
    """)


    def doozer_working = "${WORKSPACE}/doozer_working"

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
                    choice(
                        name: 'RELEASE_TYPE',
                        description: 'Select [1. Standard Release] unless discussed with team lead',
                        choices: [
                                '1. Standard Release (Named, Signed, Previous, All Channels)',
                                '2. Release Candidate (Named, Signed, Previous, Candidate Channel)',
                                '3. Feature Candidate (Named, Signed - rpms may not be, Previous, Candidate Channel)',
                                '4. Hotfix (No name, Signed, No Previous, All Channels)',
                            ].join('\n'),
                    ),
                    string(
                        name: "NIGHTLIES",
                        description: "List of proposed nightlies for each arch, separated by comma",
                        trim: true
                    ),
                    string(
                        name: 'RELEASE_OFFSET',
                        description: 'Integer. Do not specify for hotfix. If offset is X for 4.5 nightly => Release name is 4.5.X for standard, 4.5.0-rc.X for Release Candidate, 4.5.0-fc.X for Feature Candidate ',
                        trim: true,
                    ),
                    commonlib.dryrunParam('Take no actions. Note: still notifies and runs signing job (which fails)'),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    // some basic validations
    if (!params.NIGHTLIES) {
        error("You must provide a list of proposed nightlies.")
    }
    
    nightly_list = params.NIGHTLIES.split("[,\\s]+")
    if (nightly_list.size() != 3) {
        error("Something doesn't seem right. Job expects 3 nightlies of each arch")
    }
    s390x_index = nightly_list.findIndexOf { it.contains("s390x") }
    power_index = nightly_list.findIndexOf { it.contains("ppc64le") }
    x86_index = nightly_list.findIndexOf { !it.contains("s390x") && !it.contains("ppc64le") }
    if (s390x_index == -1 || power_index == -1 || x86_index == -1) {
        error("Something doesn't seem right. Job expects 3 nightlies of each arch")
    }

    common_params = [
        buildlib.param('String','RELEASE_TYPE', params.RELEASE_TYPE),
        buildlib.param('String','RELEASE_OFFSET', params.RELEASE_OFFSET),
        buildlib.param('String','ADVISORY', ""),
        booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
        booleanParam(name: 'MOCK', value: params.MOCK)
    ]

    parallel(
        "x86_64": {
            stage("x86_64") {
                def params = common_params.clone()
                nightly = nightly_list[x86_index]
                params << buildlib.param('String','FROM_RELEASE_TAG', nightly)
                
                build(
                    job: '/aos-cd-builds/build%2Fpromote',
                    propagate: false,
                    parameters: params
                )
                currentBuild.description += "<br>triggered promote: ${nightly}"
            }
        },
        "s390x": {
            stage("s390x") {
                def params = common_params.clone()
                nightly = nightly_list[s390x_index]
                params << buildlib.param('String','FROM_RELEASE_TAG', nightly)
                
                build(
                    job: '/aos-cd-builds/build%2Fpromote',
                    propagate: false,
                    parameters: params
                )
                currentBuild.description += "<br>triggered promote: ${nightly}"
            }
        },
        "ppc64le": {
            stage("ppc64le") {
                def params = common_params.clone()
                nightly = nightly_list[power_index]
                params << buildlib.param('String','FROM_RELEASE_TAG', nightly)
                
                build(
                    job: '/aos-cd-builds/build%2Fpromote',
                    propagate: false,
                    parameters: params
                )
                currentBuild.description += "<br>triggered promote: ${nightly}"
            }
        }
    )
    
    buildlib.cleanWorkspace()
}
