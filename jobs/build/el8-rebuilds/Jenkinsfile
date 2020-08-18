#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("el8-rebuilds", """
        <h2>Rebuild 4.x packages on RHEL8 for RHCOS</h2>
        This job rebuilds the openshift and openshift-clients packages against
        a RHEL 8 buildroot with exactly the same version and release as they
        were built against RHEL 7. RHCOS is the only consumer for the rebuilds.

        <b>Timing</b>: The ocp4 job runs this immediately after building any RPMs.
        The custom job runs this only after building one of the packages in question.
        It should be very rare that a human runs this directly.

        For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/el8-rebuilds/README.md" target="_blank">README</a>
    """)


    // Please update README.md if modifying parameter names or semantics
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
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: 'aos-art-automation+failed-el8-rebuilds@redhat.com',
                    ),
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )   // Please update README.md if modifying parameter names or semantics

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
