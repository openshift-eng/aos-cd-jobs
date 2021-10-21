#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sign-rhacs", """
    Signs RHACS images as a temporary measure until they are onboarded with CPaaS.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: 'REPO',
                        description: 'The image repository',
                        choices: [
                            "main",
                            "roxctl",
                            "scanner",
                            "scanner-db",
                            "collector",
                        ].join("\n"),
                    ),
                    string(
                        name: 'VERSION',
                        description: 'e.g 0.5.4.1',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'SIGNATURE_NAME',
                        description: 'Signature name\nStart with signature-1 and only increment if adding an additional signature to a release! Leave blank to auto-detect next signature',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'KEY_NAME',
                        description: 'For prod we currently use "redhatrelease2"',
                        choices: [
                            "redhatrelease2",
                        ].join("\n"),
                    ),
                    string(
                        name: 'DIGEST',
                        description: 'The digest of the release. Example value: "sha256:f28cbabd1227352fe704a00df796a4511880174042dece96233036a10ac61639"\nCan be taken from the Release job.',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.dryrunParam('Only do dry run test and exit\nDoes not send anything over the bus'),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
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

        currentBuild.displayName += "- ${params.REPO}:${params.VERSION}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " (dry-run)"
            currentBuild.description = "[DRY RUN]"
        }

        requestIdSuffix = ""

        def digest = commonlib.sanitizeInvisible(params.DIGEST).trim()
        def digestParam = digest ? "--digest ${digest}" : ""
        if ( !(digest ==~ /sha256:[0-9a-f]{64}/) ) {
            currentBuild.description = "bad digest"
            error("The digest does not look like 'sha256:hex64'")
        }

        wrap([$class: 'BuildUser']) {
            def buildUserId = (env.BUILD_USER_ID == null) ? "automated-process" : env.BUILD_USER_ID
	    if ( buildUserId == "automated-process" ) {
		echo("Automated sign request started: manually setting signing requestor")
	    }
            echo("Submitting${noop} signing requests as user: ${buildUserId}")

            dir(workDir) {
                withCredentials([file(credentialsId: 'msg-openshift-art-signatory-prod.crt', variable: 'busCertificate'),
                                 file(credentialsId: 'msg-openshift-art-signatory-prod.key', variable: 'busKey')]) {
                    // ######################################################################
                    def baseUmbParams = buildlib.cleanWhitespace("""
                                --requestor "${buildUserId}" --sig-keyname ${params.KEY_NAME}
                                --release-name "${params.VERSION}" --client-cert ${busCertificate}
                                --client-key ${busKey} --env prod
                            """)

                        def openshiftJsonSignParams = buildlib.cleanWhitespace("""
                             ${baseUmbParams} --product openshift --arch x86_64 --client-type ${params.REPO}
                             --request-id 'openshift-json-digest-${env.BUILD_ID}${requestIdSuffix}' ${digestParam} ${noop}
                         """)

                        echo "Submitting RHACS Payload JSON claim signature request"
                        retry(3) {
                            timeout(time: 3, unit: 'MINUTES') {
                                commonlib.shell(
                                    script: "../umb_producer.py json-digest ${openshiftJsonSignParams}"
                                )
                            }
                        }

                }
            }
        }
    }

    stage('mirror artifacts') {
        mirrorTarget = "use-mirror-upload.ops.rhcloud.com"
        if (params.DRY_RUN) {
            echo "Would have archived artifacts in jenkins"
            echo "Would have mirrored artifacts to mirror.openshift.com/pub/:"
            echo "    invoke_on_use_mirror push.pub.sh MIRROR_PATH"
        } else {
            echo "Mirroring artifacts to mirror.openshift.com/pub/"

            dir(workDir) {
                try {
                    SIG_NAME = params.SIGNATURE_NAME.trim()
                    if ( SIG_NAME == "" ) {
                        for (int i = 1; i < 15; i++) {
			    eqDigest = DIGEST.replace(':','=')
                            url = "http://mirror.openshift.com/pub/rhacs/signatures/rh-acs/${REPO}@${eqDigest}/signature-${i}"
                            r = httpRequest( url: url, validResponseCodes: '100:404' )
                            if ( r.status == 200 ) {
                                continue
                            } else if ( r.status == 404 ) {
                                SIG_NAME = "signature-${i}"
                                break
                            } else {
                                error("Unexpected HTTP code: ${r} ; aborting out of caution")
                            }
                        }
                        if ( SIG_NAME == "" ) {
                            error("Error finding free signature file; too many present -- please sanity check")
                        }
                    }

                    sshagent(["openshift-bot"]) {
                        withCredentials([aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                            sh """
                            set -o xtrace
                            set set -euo pipefail
                            fn=`ls sha256=*`
                            rm -rf staging
                            mv \${fn} tmpsig
                            mkdir -p \${fn}
                            mv tmpsig \${fn}/${SIG_NAME}
                            mkdir -p staging/rh-acs
                            cp -a \${fn} staging/rh-acs/${params.REPO}@\${fn}
                            mkdir -p staging/rh-acs/${params.REPO}
                            # Touch a file that indicates we have signed for this specific tag; used by rhacs-sigstore scheduled job
                            touch staging/rh-acs/${params.REPO}/${VERSION}
                            cp -a \${fn} staging/rh-acs/${params.REPO}
                            scp -r staging/* ${mirrorTarget}:/srv/pub/rhacs/signatures/
                            aws s3 sync --no-progress staging/ s3://art-srv-enterprise/pub/rhacs/signatures/
                            """
                            mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", 'rhacs/signatures')
                            if (mirror_result.contains("[FAILURE]")) {
                                echo mirror_result
                                error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                            }
                        }
                    }
                } finally {
                    echo "Archiving artifacts in jenkins:"
                    commonlib.safeArchiveArtifacts([
                        "working/cp.log",
                        "working/*.gpg",
                        "working/sha256=*",
                        ]
                    )
                }
            }
        }
    }

    buildlib.cleanWorkspace()
}
