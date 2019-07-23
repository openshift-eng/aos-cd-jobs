#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib

    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: ''
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    // [
                    //     name: 'ADVISORY',
                    //     description: 'Optional: RPM/Bug fix advisory number\nIf not provided then the default advisory will be used.',
                    //     $class: 'hudson.model.StringParameterDefinition',
                    //     defaultValue: ""
                    // ],
                    // [
                    //     name: 'BUILDS',
                    //     description: 'Optional: Only attach these brew builds (accepts numeric id or NVR)\nComma separated list\nOverrides SKIP_ADDING_BUILDS',
                    //     $class: 'hudson.model.StringParameterDefinition',
                    //     defaultValue: ""
                    // ],
                    // [
                    //     name: 'SKIP_ADDING_BUILDS',
                    //     description: 'Do not bother adding more builds\nfor example: if you are already satisfied with what is already attached and just need to run the rpmdiff/signing process',
                    //     $class: 'BooleanParameterDefinition',
                    //     defaultValue: false
                    // ],
                    // [
                    //     name: 'DRY_RUN',
                    //     description: 'Do not change anything. Just show what would have happened',
                    //     $class: 'BooleanParameterDefinition',
                    //     defaultValue: false
                    // ],
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                ]
            ],
            disableConcurrentBuilds(),
        ]
    )

    def advisory = buildlib.getDefaultAdvisoryID(params.BULID_VERSION, 'rpm')

    stage("Initialize") {
	buildlib.elliott "--version"
	buildlib.kinit()
	build.initialize()
    }
    sshagent(["openshift-bot"]) {
	stage("Advisory is NEW_FILES") { build.signedComposeStateNewFiles() }
	stage("Attach builds") { build.signedComposeAttachBuilds() }
	stage("RPM diffs ran") { build.signedComposeRpmdiffsRan(advisory) }
	stage("RPM diffs resolved") { build.signedComposeRpmdiffsResolved(advisory) }
	stage("Advisory is QE") { build.signedComposeStateQE() }
	stage("Signing completing") { build.signedComposeRpmsSigned() }
	stage("New compose") { build.signedComposeNewCompose() }
    }


    // ######################################################################
    // Email results

    //
    // ######################################################################
}
