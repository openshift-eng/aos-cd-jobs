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
                    daysToKeepStr: '',
                    numToKeepStr: '360'
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                ]
            ],
            disableConcurrentBuilds(),
        ]
    )

    echo "Initializing ${params.BUILD_VERSION} sync: #${currentBuild.number}"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def mirrorWorking = "${env.WORKSPACE}/MIRROR_working"
    // Location of the SRC=DEST input file
    def ocMirrorInput = "${mirrorWorking}/oc_mirror_input"
    // Location of the image stream to apply
    def ocIsObject = "${mirrorWorking}/release-is.yaml"
    // Locally stored image stream stub
    def baseImageStream = "/home/jenkins/base-art-latest-imagestream-${params.BUILD_VERSION}.yaml"
    // Kubeconfig allowing ART to interact with api.ci.openshift.org
    def ciKubeconfig = "/home/jenkins/kubeconfigs/art-publish.kubeconfig"

    // See 'oc image mirror --help' for more information.
    // This is the template for the SRC=DEST strings mentioned above.
    def ocFmtStr = "registry.reg-aws.openshift.com:443/{repository}=quay.io/openshift-release-dev/ocp-v${params.BUILD_VERSION}-art-dev:{version}-{release}-{image_name_short}"

    buildlib.cleanWorkdir(mirrorWorking)

    stage("Version dumps") {
        buildlib.doozer "--version"
        sh "which doozer"
        sh "oc version"
    }

    // TRY all of this so we can save the generated artifacts before
    // throwing the exceptions
    try {
        // ######################################################################
        // This should create a list of SOURCE=DEST strings in the output file
        // May take a few minutes because doozer must query brew for each image
        stage("Generate SRC=DEST input") {
            buildlib.doozer """
--working-dir "${mirrorWorking}" --group 'openshift-${params.BUILD_VERSION}'
beta:release-gen
--src-dest ${ocMirrorInput}
--image-stream ${ocIsObject}
--is-base ${baseImageStream}
'${ocFmtStr}'
"""
            images_count = sh(returnStdout: true, script: "wc -l ${ocMirrorInput}").trim().split().first()
            currentBuild.description = "Preparing to sync ${images_count} images"
        }

        // ######################################################################
        // Now run the actual mirroring command. Wrapped this in a
        // retry loop because it is known to fail occassionally
        // depending on the health of the source/destination endpoints.
        stage("oc image mirror") {
            echo "Mirror SRC=DEST input:"
            sh "cat ${ocMirrorInput}"
            try {
                retry (3) {
                    buildlib.registry_quay_dev_login()
                    buildlib.oc "image mirror --filename=${ocMirrorInput}"
		    currentBuild.description = "Success mirroring images"
                }
            } catch (mirror_error) {
                currentBuild.description = "Error mirroring images after 3 attempts:\n${mirror_error}"
                error(currentBuild.description)
            }
        }

        stage("oc apply") {
            echo "ImageStream Object to apply:"
            sh "cat ${ocIsObject}"
            try {
                buildlib.oc "apply --filename=${ocIsObject} --kubeconfig ${ciKubeconfig}"
                currentBuild.description = "Success updating image stream"

                // ######################################################################
                echo "Temporary hack while we get '4.1' CI stood up"
                // Update the image stream we produced in
                // stage(Generate SRC=DEST input) to also publish to
                // the 4.0 stream
                sh "sed -i 's/4.1-art-latest/4.0-art-latest/' ${ocIsObject}"
                buildlib.oc "apply --filename=${ocIsObject} --kubeconfig ${ciKubeconfig}"
                currentBuild.description = "Success updating both image streams"
                // End temporary hack
                // ######################################################################

            } catch (apply_error) {
                currentBuild.description = "Error updating image stream:\n${apply_error}"
                error(currentBuild.description)
            }
        }
    } finally {
        commonlib.safeArchiveArtifacts([
                "MIRROR_working/oc_mirror_input",
                "MIRROR_working/release-is.yaml"
            ]
        )
    }
}
