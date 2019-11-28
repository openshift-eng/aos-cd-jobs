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
                        name: 'ARCH',
                        description: 'The architecture for this release',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "x86_64",
                            "s390x",
                            "ppc64le",
                        ].join("\n"),
                    ],
                    [
                        name: 'NAME',
                        description: 'Release name (e.g. 4.2.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'SIGNATURE_NAME',
                        description: 'Signature name\nStart with signature-1 and only increment if adding an additional signature to a release!',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "signature-1"
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
                    ],
                    [
                        name: 'KEY_NAME',
                        description: 'Which key to sign with\nIf ENV==stage everything becomes "test"\nFor prod we currently use "redhatrelease2"',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "test",
                            "beta2",
                            "redhatrelease2",
                        ].join("\n"),
                    ],
                    [
                        name: 'DIGEST',
                        description: 'The digest of the release. Example value: "sha256=f28cbabd1227352fe704a00df796a4511880174042dece96233036a10ac61639"\nCan be taken from the Release job.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
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
        def digest = params.DIGEST ? "--digest ${params.DIGEST}" : ""

        currentBuild.displayName += "- ${params.NAME}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " (dry-run)"
            currentBuild.description += "[DRY RUN]"
        }

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
                        --request-id 'openshift-json-digest-${env.BUILD_ID}' ${digest} ${noop}
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

        mirrorTarget = "use-mirror-upload.ops.rhcloud.com"
        if (params.DRY_RUN) {
            echo "Would have archived artifacts in jenkins"
            echo "Would have mirrored artifacts to mirror.openshift.com/pub/:"
            echo "    invoke_on_use_mirror push.pub.sh MIRROR_PATH"
        } else {
            echo "Mirroring artifacts to mirror.openshift.com/pub/"

            dir(workDir) {
                try {
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

                    // transform the file into a directory containing the
                    // file, mirror to google.
		            //
		            // Notes on gsutil options:
		            // -n - no clobber/overwrite
		            // -v - print url of item
		            // -L - write to log for auto re-processing
		            // -r - recursive
                    def googleStoragePath = (params.ENV == 'stage') ? 'test-1' : 'official'
                    def gsutil = '/mnt/nfs/home/jenkins/google-cloud-sdk/bin/gsutil'  // doesn't seem to be in path
                    commonlib.shell("""
                        for file in sha256=*; do
                            mv \$file ${params.SIGNATURE_NAME}
                            mkdir \$file
                            mv ${params.SIGNATURE_NAME} \$file
                            i=1
                            until ${gsutil} cp -n -v -L cp.log -r \$file gs://openshift-release/${googleStoragePath}/signatures/openshift/release; do
                                sleep 1
                                i=\$(( \$i + 1 ))
                                if [ \$i -eq 10 ]; then echo "Failed to mirror to google after 10 attempts. Giving up."; exit 1; fi
                            done
                        done
                    """)
                    sshagent(["openshift-bot"]) {
                        def mirrorReleasePath = "openshift-v4/signatures/openshift/${(params.ENV == 'stage') ? 'test' : 'release'}"
                        sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/${mirrorReleasePath}/"
                        mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", mirrorReleasePath)
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
                    //         "product": "openshift",
                    //         "release_name": "4.1.0-rc.5",
                    //         "type": "message-digest",
                    //         "name": "sha256sum.txt.sig"
                    //     }
                    //
                    // Note that the 'product' key WILL become important when we
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
                        def mirrorReleasePath = "openshift-v4/${params.ARCH}/clients/ocp/${params.NAME}"
                        def sigFileName = (params.ENV == 'stage') ? 'sha256sum.txt.sig.test' : 'sha256sum.txt.sig'
                        sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256sum.txt.sig ${mirrorTarget}:/srv/pub/${mirrorReleasePath}/${sigFileName}"
                        mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", mirrorReleasePath)
                        if (mirror_result.contains("[FAILURE]")) {
                            echo mirror_result
                            error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                        }
                    }
                } finally {
                    echo "Archiving artifacts in jenkins:"
                    commonlib.safeArchiveArtifacts([
                        "working/cp.log",
                        "working/*.sig",
                        "working/sha256=*",
                        ]
                    )
                }
            }
        }
    }

    stage('log sync'){
        buildArtifactPath = env.WORKSPACE.replaceFirst('/working/', '/builds/')
        dirName = buildArtifactPath.split('/')[-1]
        def cmd =  "/bin/rsync --inplace -avzh ${buildArtifactPath}/[0-9]* /mnt/art-build-artifacts/signing-jobs/${dirName}"
        if (params.DRY_RUN) {
            echo "Would have run: ${cmd}"
        } else {
            sh cmd
        }
    }
}
