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
	    echo "Submitting signing requests as user: ${env.BUILD_USER}"

	    withCredentials([file(credentialsId: 'msg-openshift-art-signatory-prod.crt', variable: 'busCertificate'),
			     file(credentialsId: 'msg-openshift-art-signatory-prod.key', variable: 'busKey')]) {
		echo "Authenticating with bus cert/key at: ${busCertificate}/${busKey}"
		// Following line is for debugging when we're
		// initially testing this
		sh 'ls -l ${busCertificate} ${busKey}'

		// ######################################################################
		def baseUmbParams = buildlib.cleanWhitespace("""
                    --requestor "${env.BUILD_USER}" --sig-keyname ${params.KEY_NAME}
                    --release-name "${params.NAME}" --client-cert ${busCertificate}
                    --client-key ${busKey} --env ${params.ENV}
                """)

		// ######################################################################
		def openshiftJsonSignParams = buildlib.cleanWhitespace("""
		    ${baseUmbParams} --product openshift
		    --request-id 'openshift-json-digest ${env.BUILD_URL}' ${noop}
                """)

		echo "Submitting OpenShift Payload JSON claim signature request"
		commonlib.shell(
		    script: "./umb_producer.py json-digest ${openshiftJsonSignParams}"
		)

		// ######################################################################
		def openshiftSha256SignParams = buildlib.cleanWhitespace("""
                    ${baseUmbParams} --product openshift
                    --request-id 'openshift-message-digest ${env.BUILD_URL}' ${noop}
                """)

		echo "Submitting OpenShift sha256 message-digest signature request"
		commonlib.shell(
		    script: "./umb_producer.py message-digest ${openshiftSha256SignParams}"
		)

		// Comment this out for now. I don't think we even
		// have a sha256sum.txt file on the rhcos mirror
		// endpoint right now. Also, that url structure isn't
		// what we're going for when we hit GA.
		//
		// ######################################################################
		// def rhcosSha256SignParams = buildlib.cleanWhitespace("""
                //     ${baseUmbParams} --product rhcos
                //     --request-id 'rhcos-message-digest ${env.BUILD_URL} ${noop}'
                // """)

		// echo "Submitting RHCOS sha256 message-digest signature request"
		// res = commonlib.shell(
		//     returnAll: true,
		//     script: "./umb_producer.py message-digest ${rhcosSha256SignParams}"
		// )
	    }
	}
    }
}
