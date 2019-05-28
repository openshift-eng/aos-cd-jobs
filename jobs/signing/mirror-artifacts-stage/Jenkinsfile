#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    properties(
	[
	    pipelineTriggers(
		[
		    [
			$class: 'CIBuildTrigger',
			noSquash: false,
			providerData: [
			    $class: 'ActiveMQSubscriberProviderData',
			    checks: [
			    ],
			    name: 'signing-stage',
			    overrides: [
				topic: 'Consumer.openshift-art-signatory.stage.VirtualTopic.eng.robosignatory.art.sign'
			    ],
			    selector: '',
			    timeout: null
			]
		    ]
		]
	    )
	]
    )
    // NOTE FOR JOB PARAMETERS:
    //
    // - THIS JOB CAN RUN CONCURRENTLY. Each build will be for a
    // separate artifact and happens on-demand following successful
    // signing request responses received over the message bus.


    // This job should have a message-bus build trigger attached to
    // it. The trigger needs to the prod message bus.
    //
    // When setting up the build trigger you will need to include a
    // JMS selector. It's basically a fancy way to say "SQL
    // conditionals on a JSON object".
    //
    // The build trigger will need to listen on the topic `Consumer.openshift-art-signatory.prod.VirtualTopic.eng.robosignatory.art.sign`
    //
    // Of course, if you sign using the stage bus then that topic
    // won't work anymore. So, technically we'd need to have either:
    //
    // 1. two copies of this job, each with different listener topics
    // or
    // 2. two bus build triggers on the same job with different
    // listener topics, and the job can parse out if the response came
    // from stage or prod


    stage('collect artifact') {
	echo "${env.CI_MESSAGE}"
    }


    stage('mirror artifact') {
	// This job mirrors two different kinds of signatures.
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

	// ######################################################################

	// How do you differentiate between the responses? Once you
	// have the response object you will examine the
	// 'artifact_meta' object. For reference, we SEND that object
	// when we submit the signing request. For example:
	//
	// * Request to sign a JSON digest, 'artifact_meta' could look
	// like this:
	//
	//     "artifact_meta": {
	//	 "product": "openshift",
	//	 "release_name": "4.1.0-rc.5",
	//	 "type": "json-digest",
	//	 "name": "sha256=dc67ad5edd91ca48402309fe0629593e5ae3333435ef8d0bc52c2b62ca725021"
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


    }

    stage ('archive artifacts') {
	/* We have been requested to archive any artifacts we receive
	as part of the signing process. */
    }
}
