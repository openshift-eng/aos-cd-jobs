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
            disableConcurrentBuilds(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-art-automation+failed-rhcos-puddle@redhat.com',
                    ],
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    def buildExceptions = []
    def puddleVersions = ["4.1", "4.2", "4.3"]
    puddleVersions.each { version ->
        try {
            buildlib.kinit()
            stage("rpm rebuilds for ${version}") {
                def builds = [
                    "openshift": {
                        commonlib.shell("./rebuild_rpm.sh openshift ${version}")
                    }
                ]
                if (version != "4.1") {
                    // in 4.2+ openshift-clients is split out to its own package
                    builds["clients"] = {
                        sleep 2 // because commonlib.shell init isn't safe for concurrency.
                        // TODO: find the card I know I wrote explaining that.
                        commonlib.shell("./rebuild_rpm.sh openshift-clients ${version}")
                    }
                }
                parallel builds
            }
        } catch(e) {
            // still run puddle when the rpm build fails
            echo "Package build failed:\n${e}"
            buildExceptions << e
            currentBuild.result = "FAILURE"
        }

        stage("run puddle for ${version}") {
            try {
                echo "Initializing puddle build #${currentBuild.number} for Openshift version ${version}"

                def puddleConf = "https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/puddle-conf/atomic_openshift-${version}.el8.conf"

                puddle = buildlib.build_puddle(
                    puddleConf,
                    null,
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n"    // do not send an email for this puddle
                )

                echo "View the package list here: http://download.lab.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${version}-el8/latest/x86_64/os/Packages/"
            } catch(e) {
                // still run next version if puddle fails
                echo "Puddle failed:\n${e}"
                buildExceptions << e
                currentBuild.result = "FAILURE"
            }
        }
    }

    if (buildExceptions) {
        err = buildExceptions[0]
        currentBuild.description = "\nerror: ${err.getMessage()}"
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error building RPMs and puddles for RHCOS",
            body: "Encountered ${buildExceptions.size()} error(s) while running pipeline:\n${buildExceptions}",
        )
        throw err
    }
}
