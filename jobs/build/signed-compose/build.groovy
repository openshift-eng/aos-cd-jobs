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

// Set the advisory to the NEW_FILES state (allows builds to be added)
def signedComposeStateNewFiles() {
    buildlib.elliott("${elliottOpts} change-state --state NEW_FILES ${advisoryOpt}")
}

// Search brew for, and then attach, any viable builds. Do this for
// EL7 and EL8.
def signedComposeAttachBuilds() {
    // Don't actually attach builds if this is just a dry run
    def advs = (params.DRY_RUN == true) ? advisoryOpt : ''
    def cmd = "${elliottOpts} find-builds --kind rpm ${advs}"
    def cmdEl8 = "${elliottOpts} --branch rhaos-${params.BUILD_VERSION}-rhel-8 find-builds --kind rpm ${advs}"

    try {
        def attachResult = buildlib.elliott(cmd, [capture: true]).trim().split('\n')[-1]
        def attachResultEl8 = buildlib.elliott(cmdEl8, [capture: true]).trim().split('\n')[-1]
    } catch (err) {
        echo("Problem running elliott")
        currentBuild.description += """
----------------------------------------
${err}
----------------------------------------"""
        error("Could not process a find-builds command")
    }
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
    echo "Action may be required: Complete any pending RPM Diff waivers to continue. Pending diffs will be printed."

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
    buildlib.elliott("${elliottOpts} change-state --state QE ${advisoryOpt}")
}

// Poll the 'signed' status of all builds attached to the advisory. We
// wrap this in a retry() because some times the builds won't get
// signed in a reasonable amount of time (10 minutes). To account for
// that possible condition we frob the state between NEW_FILES and
// QE. Re-entering the QE state triggers the signing mechanism again.
def signedComposeRpmsSigned() {
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

// Create a new RHEL7 compose. Take note of the following:
//
// The `puddle` command (which this step invokes) *REQUIRES* that the
// user running it (ocp-build, in this case) has a valid kerberos
// ticket. To ensure that this is ready and available for our use case
// we must ensure a few things happen:
//
// * The `jenkins` user has enabled kerberos `ticket forwarding`
//   option. When running `kinit` we *MUST* include the `-f` option
//   flag. This requests a `forwardable` ticket for the user.
//
// * Additionally, ensure that the `jenkins` user has the:
//
//     `GSSAPIDelegateCredentials yes`
//
//  option set in their ~/.ssh/config file like this:
//
//     Host rcm-guest rcm-guest.app.eng.bos.redhat.com
//     Hostname                   rcm-guest.app.eng.bos.redhat.com
//     User                       ocp-build
//     GSSAPIDelegateCredentials  yes
//
// That last line there, will tell the `ssh` command to try to
// authenticate using GSSAPI (kerberos, in our case) credentials.
//
// FINALLY, the user on the remote end (`ocp-build`) *MUST* have their
// `~/.k5login` file configured to include the principal we're
// authenticating with.
def signedComposeNewComposeEl7() {
    if ( params.DRY_RUN ) {
        currentBuild.description += "\nDry-run: EL7 Compose not actually built"
        echo("Skipping running puddle. Would have used whitelist: ${errataList}")
    } else {
        def cmd = "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s ${buildlib.args_to_string(params.BUILD_VERSION, errataList)} < ${env.WORKSPACE}/build-scripts/rcm-guest/call_puddle_advisory.sh"
        def result = commonlib.shell(
            script: cmd,
            returnAll: true,
        )

        if ( result.returnStatus != 0 ) {
            mailForFailure(result.combined)
            error("Error running puddle command")
        }
    }
}

// Create a new signed RHEL8 puddle. This is a work-around of sorts.
//
// Due to limitations in 'puddle' (which is deprecated) we have to
// assemble a RHEL8 brew tag with signed packages MANUALLY. This
// script (ocp-tag-signed-errata-builds.py) was provided by Ryan
// Hartman from RCM. This replaces our former process (pre September
// 2019) wherein we would have to submit a ticket to RCM to have
// packages assembled into a constantly changing brew tag.
//
// Now, using this new process, we skip making a ticket. Instead, our
// build account (kerberos principal:
// ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM) has been
// given permission to add packages into the new tags for RHEL8.
def signedComposeNewComposeEl8() {
    def tagCmd = "./ocp-tag-signed-errata-builds.py --errata-group RHOSE-${params.BUILD_VERSION} --errata-group 'RHOSE ASYNC' --errata-product RHOSE --errata-product-version OSE-${params.BUILD_VERSION}-RHEL-8 --brew-pending-tag rhaos-${params.BUILD_VERSION}-rhel-8-image-build --verbose"

    if ( params.DRY_RUN ) {
        currentBuild.description += "\nDry-run: EL8 Compose not actually built"
        echo("Packages which would have been added to rhaos-${params.BUILD_VERSION}-rhel-8-image-build tag:")
        def testTagCmd = cmd + " --test"
        def tagResult = commonlib.shell(
            script: testTagCmd,
            returnAll: true,
        )

        echo("Sleeping 10 seconds to give brew some time to catch up")
        sleep 10

        if ( tagResult.returnStatus == 0 ) {
            echo(tagResult.stdout)
        } else {
            echo()
            error("""Error running test tag assembly:
----------------------------------------
${tagResult.combined}
----------------------------------------
""")
        }
    } else {
        echo("Updating RHEL8 brew tag")
        def tagResult = commonlib.shell(
            script: tagCmd,
            returnAll: true,
        )

        echo("Sleeping 10 seconds to give brew some time to catch up")
        sleep 10

        if ( tagResult.returnStatus == 0 ) {
            def newPkgs = []
            def untaggedPkgs = []
            for ( line in tagResult.stdout.split('\n') ) {
                if ( line.contains('tag_builds') ) {
                    newPkgs.add(line.split(' ')[3])
                } else if ( line.contains('untag_builds') ) {
                    untaggedPkgs.add(line.split(' ')[3])
                }
            }

            if ( newPkgs.size() > 0 ) {
                currentBuild.description += "\n${newPkgs.size()} packages added to RHEL8 tag"
                currentBuild.description += "\n${untaggedPkgs.size()} packages removed from RHEL8 tag"
                currentBuild.displayName += " [+${newPkgs.size()}/-${untaggedPkgs.size()} EL8]"
            }
        } else {
            mailForFailure(tagResult.combined)
            error("""Error running tag assembly:
----------------------------------------
${tagResult.combined}
----------------------------------------
""")
        }

        echo("Building RHEL8 puddle")
        def puddleCmd = "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s ${buildlib.args_to_string(params.BUILD_VERSION)} < ${env.WORKSPACE}/build-scripts/rcm-guest/call_puddle_advisory_el8.sh"
        def puddleResult = commonlib.shell(
            script: puddleCmd,
            returnAll: true,
        )

        if ( puddleResult.returnStatus == 0 ) {
            echo("View the package list here: ${puddleURL}-el8")
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
    def puddleMetaEl8 = analyzePuddleLogs('-el8')
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


return this
