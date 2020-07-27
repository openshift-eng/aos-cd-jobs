#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '60',
                    numToKeepStr: ''
                )
            ),
            disableResume(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-art-automation+failed-el8-rebuilds@redhat.com',
                    ],
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    def version = params.BUILD_VERSION
    currentBuild.displayName += " - ${version}"
    try {
        buildlib.kinit()
        def builds = [
            "openshift": {
                stage("openshift RPM") {
                    commonlib.shell("./rebuild_rpm.sh openshift ${version}")
                }
            },
            "clients": {
                stage("openshift-clients RPM") {
                    commonlib.shell("./rebuild_rpm.sh openshift-clients ${version}")
                }
            }
        ]
        parallel builds
    } catch(err) {
        echo "Package build failed:\n${err}"
        currentBuild.result = "FAILURE"
        currentBuild.description = "\nerror: ${err.getMessage()}"
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error rebuilding ${version} el8 RPMs for RHCOS",
            body: "Encountered error(s) while running pipeline:\n${err}",
        )
        throw err
    }
}
