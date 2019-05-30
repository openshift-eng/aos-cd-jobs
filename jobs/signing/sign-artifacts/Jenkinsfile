#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'NAME',
                        description: 'Release name (e.g. 4.1.0-rc.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DRY_RUN',
                        description: 'Only do dry run test and exit.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'ENV',
                        description: 'Which environment to sign in',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "stage",
                            "prod",
                        ].join("\n"),
                        defaultValue: "stage"
                    ],
                    [
                        name: 'KEY_NAME',
                        description: 'Which key to sign with (if ENV==stage, everything becomes "test")',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "test",
                            "beta2",
			    "redhatrelease2",
                        ].join("\n"),
                        defaultValue: "test"
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    def workDir = "${env.WORKSPACE}/working"
    buildlib.cleanWorkdir(workDir)

    // must be able to access remote registry for verification
    buildlib.registry_quay_dev_login()

    stage('sign-artifacts') {
        def noop = params.DRY_RUN ? " --noop" : " "

        wrap([$class: 'BuildUser']) {
            echo "Submitting signing requests as user: ${env.BUILD_USER_ID}"

            dir(workDir) {

                withCredentials([file(credentialsId: 'msg-openshift-art-signatory-prod.crt', variable: 'busCertificate'),
                                 file(credentialsId: 'msg-openshift-art-signatory-prod.key', variable: 'busKey')]) {
                    echo "Authenticating with bus cert/key at: ${busCertificate}/${busKey}"
                    // Following line is for debugging when we're
                    // initially testing this
                    sh 'ls -l ${busCertificate} ${busKey}'

                    // ######################################################################
                    def baseUmbParams = buildlib.cleanWhitespace("""
                                --requestor "${env.BUILD_USER_ID}" --sig-keyname ${params.KEY_NAME}
                                --release-name "${params.NAME}" --client-cert ${busCertificate}
                                --client-key ${busKey} --env ${params.ENV}
                            """)

                    // ######################################################################
                    def openshiftJsonSignParams = buildlib.cleanWhitespace("""
                        ${baseUmbParams} --product openshift
                        --request-id 'openshift-json-digest-${env.BUILD_ID}' ${noop}
                            """)

                    echo "Submitting OpenShift Payload JSON claim signature request"
                    commonlib.shell(
                        script: "../umb_producer.py json-digest ${openshiftJsonSignParams}"
                    )

                    // ######################################################################
                    def openshiftSha256SignParams = buildlib.cleanWhitespace("""
                                ${baseUmbParams} --product openshift
                                --request-id 'openshift-message-digest-${env.BUILD_ID}' ${noop}
                            """)

                    echo "Submitting OpenShift sha256 message-digest signature request"
                    commonlib.shell(
                        script: "../umb_producer.py message-digest ${openshiftSha256SignParams}"
                    )

                    // Comment this out for now. I don't think we even
                    // have a sha256sum.txt file on the rhcos mirror
                    // endpoint right now. Also, that url structure isn't
                    // what we're going for when we hit GA.
                    //
                    // ######################################################################
                    // def rhcosSha256SignParams = buildlib.cleanWhitespace("""
                            //     ${baseUmbParams} --product rhcos
                            //     --request-id 'rhcos-message-digest-${env.BUILD_ID} ${noop}'
                            // """)

                    // echo "Submitting RHCOS sha256 message-digest signature request"
                    // res = commonlib.shell(
                    //     returnAll: true,
                    //     script: "../umb_producer.py message-digest ${rhcosSha256SignParams}"
                    // )
                }
            }
        }
    }

    stage('mirror artifacts') {
        // This job mirrors two different kinds of signatures.
        //
        // 1) JSON digest claims, they are signatures for the release
        // payload, stored in a JSON format.
        //
        // 2) Message digests, they are sha256sum.txt files which have
        // sha digests for a directory of contents

        // ######################################################################

        // Old comment preserved for context. Feel free to remove once
        // implemented:
        //
        // <OLD-COMMENT>
        // How do you differentiate between the responses? Once you
        // have the response object you will examine the
        // 'artifact_meta' object. For reference, we SEND that object
        // when we submit the signing request. For example:
        //
        // * Request to sign a JSON digest, 'artifact_meta' could look
        // like this:
        //
        //     "artifact_meta": {
        //	     "product": "openshift",
        //	     "release_name": "4.1.0-rc.5",
        //	     "type": "json-digest",
        //	     "name": "sha256=dc67ad5edd91ca48402309fe0629593e5ae3333435ef8d0bc52c2b62ca725021"
        //     }
        //
        // We receive that same object back in the signing
        // response. Look at .artifact_meta.type and see it says
        // 'json-digest'. This means it falls under mirroring location
        // (1) from above. We can fill in the mirroring location using
        // the information from the response object.
        //
        // signatures/openshift/release/`.artifact_meta.name`/signature-1
        //
        // </OLD-COMMENT>

        MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
        if(params.DRY_RUN) {
            echo "Would have archived artifacts in jenkins"
            echo "Would have mirrored artifacts to mirror.openshift.com/pub/:"
            echo "    invoke_on_use_mirror push.pub.sh MIRROR_PATH" 
        } else {
            echo "Archiving artifacts in jenkins:"
            commonlib.safeArchiveArtifacts([
                "sha256=*",
                "*.sig",
                "working/*.sig",
                "working/sha256=*",
            ])
            echo "Mirroring artifacts to mirror.openshift.com/pub/"

            dir(workDir) {
                // ######################################################################

                // the umb producer script should have generated two
                // files. One is a 'sha26=.......' and one is
                // 'sha256sum.txt.sig'

                // sha256=...........
                //
                // 1) JSON digest claims. They get mirrored to
                // mirror.openshift.com/pub/openshift-v4/ using this directory
                // structure:
                //
                // signatures/openshift/release/
                //   -> sha256=<IMAGE-DIGEST>/signature-1
                //
                // where <IMAGE-DIGEST> is the digest of the payload image and
                // the signed artifact is 'signature-1'
                //
                // 2) A message digest (sha256sum.txt) is mirrored to
                // https://mirror.openshift.com/pub/openshift-v4/clients/
                // using this directory structure:
                //
                // ocp/
                //  -> <RELEASE-NAME>/sha256sum.txt.sig
                //
                // where <RELEASE-NAME> is something like '4.1.0-rc.5'

                // transform the file into a directory containing the file
                commonlib.shell('''
                    for file in sha256=*; do
                        mv $file signature-1
                        mkdir $file
                        mv signature-1 $file
                    done
                ''')
                sshagent(["openshift-bot"]) {
                    MIRROR_PATH = "openshift-v4/signatures/openshift/release"
                    sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${MIRROR_TARGET}:/srv/pub/${MIRROR_PATH}/"
                    mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", MIRROR_PATH)
                    if (mirror_result.contains("[FAILURE]")) {
                        echo mirror_result
                        error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                    }
                }

                // ######################################################################

                // sha256sum.txt.sig
                //
                // For message digests (mirroring type 2) we'll see instead
                // that .artifact_meta.type says 'message-digest'. Take this
                // for example (request to sign the sha256sum.txt file from
                // 4.1.0-rc.5):
                //
                //     "artifact_meta": {
                //	 "product": "openshift",
                //	 "release_name": "4.1.0-rc.5",
                //	 "type": "message-digest",
                //	 "name": "sha256sum.txt.sig"
                //     }
                //
                // Note that the 'product' key will become important when we
                // are sending RHCOS bare metal message-digests in the
                // future. From the .artifact_meta above we know that we have
                // just received the sha256sum.txt.sig file for openshift
                // release 4.1.0-rc.5. We will mirror this file to:
                //
                // https://mirror.openshift.com/pub/openshift-v4/clients/
                //  --> ocp/
                //  ----> `.artifacts.name`/
                //  ------> sha256sum.txt.sig
                //  ==> https://mirror.openshift.com/pub/openshift-v4/clients/ocp/4.1.0-rc.5/sha256sum.txt.sig

                sshagent(["openshift-bot"]) {
                    MIRROR_PATH = "openshift-v4/clients/ocp/${params.NAME}"
                    sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256sum.txt.sig ${MIRROR_TARGET}:/srv/pub/${MIRROR_PATH}/sha256sum.txt.sig"
                    mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", MIRROR_PATH)
                    if (mirror_result.contains("[FAILURE]")) {
                        echo mirror_result
                        error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                    }
                }
            }
        }
    }
}
