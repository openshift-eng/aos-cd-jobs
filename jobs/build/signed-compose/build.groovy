buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// We'll update this later
elliottOpts = ""
advisoryOpt = "--use-default-advisory rpm"

def initialize(advisory) {
    elliottOpts += "--group=openshift-${params.BUILD_VERSION}"
    echo "${currentBuild.DisplayName}: https://errata.devel.redhat.com/advisory/${advisory}"
}

def signedComposeStateNewFiles() {
    buildlib.elliott "${elliottOpts} change-state --state NEW_FILES ${advisoryOpt}"
}

def signedComposeAttachBuilds() {
    buildlib.elliott "${elliottOpts} find-builds --kind rpm ${advisoryOpt}"
}

def signedComposeRpmdiffsRan(advisory) {
    commonlib.shell(
	// script auto-waits 60 seconds and re-retries until completed
	script: "./rpmdiff.py check-ran ${advisory}",
    )
}

def signedComposeRpmdiffsResolved(advisory) {
    echo "Action may be required: Complete any pending RPM Diff waivers to continue. Pending diffs will be printed."

    def stderr, stdout, res = commonlib.shell(
	script: "./rpmdiff.py check-resolved {$advisory}", returnAll: true
    )

    if (res != 0) {
	mailForResolution(stdout)
	// email people to have somebody take care of business
	def resp = input message: "Action required: Complete any pending RPM Diff waivers to continue",
        parameters: [
	    [
                $class: 'hudson.model.ChoiceParameterDefinition',
                choices: "CONTINUE\nABORT",
                name: 'action',
                description: 'CONTINUE if all RPM diffs have been waived. ABORT (terminate the pipeline) to stop this job.'
	    ]
        ]

        switch (resp) {
	    case "CONTINUE":
                echo "RPM Diffs are resolved. Continuing to make signed puddle"
                return true
	    default:
                error("User chose to abort pipeline after reviewing RPM Diff waivers")
        }
    }
}

def signedComposeStateQE() {
    buildlib.elliott "${elliottOpts} change-state --state QE ${advisoryOpt}"
}

def signedComposeRpmsSigned() {
    buildlib.elliott "${elliottOpts} poll-signed ${adisoryOpt}"
}

def signedComposeNewCompose() {
    echo "Puddle a signed compose including the errata"

    def errataList = buildlib.getErrataWhitelist(params.BUILD_VERSION)
    buildlib.invoke_on_rcm_guest("call_puddle_advisory.sh", params.BUILD_VERSION, errataList)

    echo "View the package list here: http://download.lab.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${params.BUILD_VERSION}/latest/x86_64/os/Packages/"
}

def mailForResolution(diffs) {
    def buildURL = env.BUILD_URL.replace('https://buildvm.openshift.eng.bos.redhat.com:8443', 'https://localhost:8888')
    def diffMessage = """
Manual RPM Diff resolution is required for the generation of an
ongoing signed-compose. Please review the RPM Diffs below and resolve
them as soon as possible.

${diffs}

After the RPM Diffs have been resolved please return to the
in-progress compose job and choose the CONTINUE option.

    - Jenkins job: ${buildURL}
"""

    commonlib.email(
        to: "aos-art-automation@redhat.com",
        from: "aos-art-automation+rpmdiff-resolution@redhat.com",
        replyTo: "aos-team-art@redhat.com",
	subject: "RPM Diffs require resolution for signed compose: ${currentBuild.number}",
	body: diffMessage
    )
}

return this
