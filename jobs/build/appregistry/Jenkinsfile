node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '25')
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-team-art@redhat.com',
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    buildlib.initialize(false)

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(DOOZER_WORKING)

    currentBuild.description = "Collecting appregistry images for ${params.BUILD_VERSION}"

    try {
        sshagent(["openshift-bot"]) {
            stage("fetch appregistry images") {
                buildlib.doozer "--working-dir ${DOOZER_WORKING} --group 'openshift-${params.BUILD_VERSION}' images:print --label 'com.redhat.delivery.appregistry' --short '{label},{name},{build},{version}' | tee ${env.WORKSPACE}/appreg.list"

                sh "python appreg.py ${env.WORKSPACE}/appreg.list ${env.WORKSPACE}/appreg.yaml"
            }

            currentBuild.description = "appregistry images collected for ${params.BUILD_VERSION}"
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Unexpected error during OCP Merge!",
            body: "Encountered an unexpected error while running OCP merge: ${err}"
        )

        currentBuild.description = "Failed collecting appregistry images for ${params.BUILD_VERSION}"

        throw err
    } finally {
        commonlib.safeArchiveArtifacts([
            "${env.WORKSPACE}/appreg.yaml"
        ])
    }
}
