buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// We'll update this later
elliottOpts = ""
advisoryOpt = "--use-default-advisory rpm"
errataList = ""
puddleURL = "http://download.lab.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift-signed/${params.BUILD_VERSION}"
workdir = "puddleWorking"
// Substitute the advisory ID in later
rpmDiffsUrl = "https://errata.devel.redhat.com/advisory/ID/rpmdiff_runs"

def initialize(advisory) {
    buildlib.cleanWorkdir(workdir)
    elliottOpts += "--group=openshift-${params.BUILD_VERSION}"
    echo("${currentBuild.displayName}: https://errata.devel.redhat.com/advisory/${advisory}")
    rpmDiffsUrl = rpmDiffsUrl.replace("ID", advisory)
    errataList += buildlib.elliott("${elliottOpts} puddle-advisories", [capture: true]).trim().replace(' ', '')
    currentBuild.description = "Signed puddle for advisory https://errata.devel.redhat.com/advisory/${advisory}"
    currentBuild.description += "\nErrata whitelist: ${errataList}"
}

// Search brew for, and then attach, any viable builds. Do this for
// EL7 and EL8.
def signedComposeAttachBuilds() {
    if (!params.ATTACH_BUILDS) {
        echo("Job configured not to attach builds; continuing using builds already attached")
        return
    }
    if (params.DRY_RUN) {
        echo("Skipping attach builds to advisory for dry run")
        return
    }
    buildlib.attachBuildsToAdvisory(["rpm"], params.BUILD_VERSION)
}

// Monitor and wait for all of the RPM diffs to run.
//
// @param <String> advisory: The ID of the advisory to watch
def signedComposeRpmdiffsRan(advisory) {
    commonlib.shell(
        // script auto-waits 60 seconds and re-retries until completed
        script: "./rpmdiff.py check-ran ${advisory}",
    )
}

// Check that each of the RPM Diffs for the given advisory have been
// resolved (waived/passed). RPM Diffs that require human intervention
// will be collected and then later emailed out to the team.
//
// The job will block here until the diffs are resolved and someone
// presses the `CONTINUE` button.
//
// @param <String> advisory: The ID of the advisory to check
def signedComposeRpmdiffsResolved(advisory) {
    echo("Action may be required: Complete any pending RPM Diff waivers to continue. Pending diffs will be printed.")

    def result = commonlib.shell(
        script: "./rpmdiff.py check-resolved ${advisory}",
        returnAll: true
    )

    if (result.returnStatus != 0) {
        currentBuild.description += "\nRPM Diff resolution required"
        mailForResolution(result.stdout)
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
                echo("RPM Diffs are resolved. Continuing to make signed puddle")
                return true
            default:
                error("User chose to abort pipeline after reviewing RPM Diff waivers")
        }
    }
}

// Put the advisory into the QE state. This will trigger the
// build-signing mechanism. You might call this more than once if
// you're having trouble getting a build to get signed in a reasonable
// amount of time (10 minutes).
def signedComposeStateQE() {
    if (params.DRY_RUN) {
        echo("Skipping advisory state change for dry run.")
        echo("would have run: ${elliottOpts} change-state --state QE ${advisoryOpt}")
        return
    }
    if (params.KEEP_ADVISORY_STATE) {
        echo("Would not change the state of adivosry since KEEP_ADVISORY_STATE was checked.")
        return
    }
    def seconds = 0
    retry(3) {
        sleep seconds
        seconds = seconds + 30
        out = buildlib.elliott("${elliottOpts} change-state --state QE ${advisoryOpt}", [capture: true])
        echo("${out}")
    }
}

// Poll the 'signed' status of all builds attached to the advisory. We
// wrap this in a retry() because some times the builds won't get
// signed in a reasonable amount of time (10 minutes). To account for
// that possible condition we frob the state between NEW_FILES and
// QE. Re-entering the QE state triggers the signing mechanism again.
def signedComposeRpmsSigned() {
    if (params.DRY_RUN) {
        currentBuild.description += "\nDry-run: not actually signing any new builds"
        echo("Skipping signing packages for dry run.")
        echo("would have run: ${elliottOpts} poll-signed --minutes=10 ${advisoryOpt}")
        return
    }
    def signed = false
    retry(3) {
        try {
            buildlib.elliott("${elliottOpts} poll-signed --minutes=10 ${advisoryOpt}")
            signed = true
        } catch (err) {
            signedComposeStateNewFiles()
            // Give it a chance to catch up. ET can be slow
            sleep 5
            signedComposeStateQE()
        } finally {
            if ( !signed ) {
                error("Failed to get all builds to 'signed' status after 3 retries")
            }
        }
    }
}

// Create a new signed puddle. This is a work-around of sorts.
//
// Due to limitations in 'puddle' (which is deprecated) we have to
// assemble a brew tag with signed packages MANUALLY. This
// script (ocp-tag-signed-errata-builds.py) was provided by Ryan
// Hartman from RCM. This replaces our former process (pre September
// 2019) wherein we would have to submit a ticket to RCM to have
// packages assembled into a constantly changing brew tag for el8,
// and turns out to be better for el7 too.
//
// Now, using this new process, we skip making a ticket. Instead, our
// build account (kerberos principal:
// ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM) has been
// given permission to add packages into the new tags.
def signedComposeNewCompose(elMajor="8") {
    def signedTag = "rhaos-${params.BUILD_VERSION}-rhel-${elMajor}-image-build"
    // one of the things that changed with RHEL 8 is the product version convention
    def productVersion = elMajor == "7" ? "RHEL-7-OSE-${params.BUILD_VERSION}" : "OSE-${params.BUILD_VERSION}-RHEL-8"
    def elliott_args = " --debug tag-builds --tag ${signedTag} --product-version ${productVersion}"
    for (advisory in errataList.split(",")) {
        elliott_args += " --advisory ${advisory}"
    }
    if ( params.DRY_RUN ) {
        currentBuild.description += "\nDry-run: EL${elMajor} Compose not actually built"
        echo("Packages which would have been added to ${signedTag} tag:")
        buildlib.elliott("${elliottOpts} ${elliott_args} --dry-run")
    } else {
        // It appears that two simultaneous tag requests for the same package, even on
        // different releases, causes both API calls to hang.  Use lock to prevent this.
        lock('update-brew-tags') {
            echo("Updating RHEL${elMajor} brew tag")
            timeout(time: 15, unit: 'MINUTES') {
                buildlib.elliott("${elliottOpts} ${elliott_args}")
            }
        }

        echo("Sleeping 2 minutes to give brew some time to catch up")
        sleep 120

        echo("Building RHEL${elMajor} puddle")
        def puddleCmd = "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s ${buildlib.args_to_string(params.BUILD_VERSION)} el${elMajor} < ${env.WORKSPACE}/build-scripts/rcm-guest/call_puddle_signed_tag.sh"
        def puddleResult = commonlib.shell(
            script: puddleCmd,
            returnAll: true,
        )

        if ( puddleResult.returnStatus == 0 ) {
            echo("View the package list here: ${puddleURL}${elMajor == '8' ? '-el8' : ''}")
        } else {
            mailForFailure(puddleResult.combined)
            error("Error running puddle command")
        }
    }
}

// We did it! This grabs puddle logs to give us data required to
// format a useful email.
def mailForSuccess() {
    def puddleMetaEl7 = analyzePuddleLogs()
    def puddleMetaEl8 = requiresRhel8() ? analyzePuddleLogs('-el8') : ["newPuddle": "n/a", "changeLog": "n/a"]

    def successMessage = """New signed composes created for OpenShift ${params.BUILD_VERSION}

  Errata Whitelist included advisories: ${errataList}
  EL7 Puddle URL: ${puddleMetaEl7.newPuddle}
  EL8 Puddle URL: ${puddleMetaEl8.newPuddle}
  Jenkins Console Log: ${commonlib.buildURL('console')}

Puddle Changelog EL7:
######################################################################
${puddleMetaEl7.changeLog}
######################################################################

Puddle Changelog EL8:
######################################################################
${puddleMetaEl8.changeLog}
######################################################################

"""

    echo("Mailing success message: ")
    echo(successMessage)

    commonlib.email(
        // to: "aos-art-automation@redhat.com",
        to: params.MAIL_LIST_SUCCESS,
        from: "aos-art-automation+new-signed-compose@redhat.com",
        replyTo: "aos-team-art@redhat.com",
        subject: "New signed compose for OpenShift ${params.BUILD_VERSION} job #${currentBuild.number}",
        body: successMessage,
    )
}

// @param <String> err: Error message from failed command
def mailForFailure(String err) {
    def failureMessage = """Error creating new signed compose OpenShift ${params.BUILD_VERSION}

  Errata Whitelist included advisories: ${errataList}
  Jenkins Console Log: ${commonlib.buildURL('console')}

######################################################################
${err}
######################################################################

"""

    echo("Mailing failure message: ")
    echo(failureMessage)

    commonlib.email(
        // to: "aos-art-automation@redhat.com",
        to: params.MAIL_LIST_FAILURE,
        from: "aos-art-automation+failed-signed-compose@redhat.com",
        replyTo: "aos-team-art@redhat.com",
        subject: "Error creating new signed compose for OpenShift ${params.BUILD_VERSION} job #${currentBuild.number}",
        body: failureMessage,
    )
}

// RPM Diffs have ran, however, they are not all resolved/waived. Send
// out a notice to the team so someone can complete the remaining
// diffs.
//
// @param <String> diffs: A string with the status of EACH remaining
// diff, what RPM is being diffed, and the URL to resolve the diff
def mailForResolution(diffs) {
    def diffMessage = """
Manual RPM Diff resolution is required for the generation of an
ongoing signed-compose. Please review the RPM Diffs below and resolve
them as soon as possible.

View all RPM Diffs: ${rpmDiffsUrl}
----------------------------------------
${diffs}
----------------------------------------

After the RPM Diffs have been resolved please return to the
in-progress compose job and choose the CONTINUE option.

    - Jenkins job: ${commonlib.buildURL('input')}
"""

    commonlib.email(
        // to: "aos-art-automation@redhat.com",
        to: params.MAIL_LIST_FAILURE,
        from: "aos-art-automation+rpmdiff-resolution@redhat.com",
        replyTo: "aos-team-art@redhat.com",
        subject: "RPM Diffs require resolution for signed compose: ${currentBuild.number}",
        body: diffMessage,
    )
}

// ######################################################################
// Some utility functions
// ######################################################################

// Get data from the logs of the newly created puddle. Will download
// the puddle.log and changelog.log files for archiving. Uses the
// global `puddleURL` variable to get the initial log. This log is
// parsed to identify the unique tag (`latestTag`) of the new puddle.
//
// @params <String> dist: Prefixed with a hyphen '-', a short
// distribution name. For example: '-el8'. Absent (default) will pull
// standard puddle logs, which are el7.
//
// @return <Object> (map) with keys:
// - String changeLog: The full changelog
// - String puddleLog: The full build log
// - String latestTag: The YYYY-MM-DD.i tag of the puddle, where 'i'
//   is a monotonically increasing integer
// - String newPuddle: Full URL to the new puddle base directory
def analyzePuddleLogs(String dist='') {
    dir(workdir) {
        // Get the generic 'latest', it will tell us the actual name of this new puddle
        commonlib.shell("wget ${puddleURL}${dist}/latest/logs/puddle.log -O puddle${dist}.log")
        // This the tag of our newly created puddle
        def latestTag = commonlib.shell(
            script: "awk -n '/now points to/{print \$NF}' puddle${dist}.log",
            returnStdout: true,
        ).trim()

        currentBuild.description += "\nTag${dist}: ${latestTag}"
        // Form the canonical URL to our new puddle
        def newPuddle = "${puddleURL}${dist}/${latestTag}"

        currentBuild.description += "Puddle: ${newPuddle}"
        // Save the changelog for emailing out
        commonlib.shell("wget ${newPuddle}/logs/changelog.log -O changelog${dist}.log")

        return [
            changeLog: readFile("changelog${dist}.log"),
            puddleLog: readFile("puddle${dist}.log"),
            latestTag: latestTag,
            newPuddle: newPuddle,
        ]
    }
}

// Does this version require the rhel 8 branch and compose?
// Only if it's 4.x+
def requiresRhel8(version=null) {
    return !(version ?: params.BUILD_VERSION).startsWith("3.")
}

return this
