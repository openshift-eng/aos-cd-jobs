buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib


def initialize() {
    buildlib.cleanWorkdir(workdir)
    // echo("${currentBuild.displayName}: ${params.RELEASE_URL}")
    // rpmDiffsUrl = rpmDiffsUrl.replace("ID", advisory)
    // errataList += buildlib.elliott("${elliottOpts} puddle-advisories", [capture: true]).trim().replace(' ', '')
    // currentBuild.description = "Signed puddle for advisory https://errata.devel.redhat.com/advisory/${advisory}"
    // currentBuild.description += "\nErrata whitelist: ${errataList}"
}

// def signedComposeAttachBuilds() {
//     // Don't actually attach builds if this is just a dry run
//     def advs = params.DRY_RUN ? '' : advisoryOpt
//     def cmd = "${elliottOpts} find-builds --kind rpm ${advs}"
//     def cmdEl8 = "${elliottOpts} --branch rhaos-${params.BUILD_VERSION}-rhel-8 find-builds --kind rpm ${advs}"

//     try {
//         buildlib.elliott(cmd, [capture: true]).trim().split('\n')[-1]
//         if (requiresRhel8()) {
//             buildlib.elliott(cmdEl8, [capture: true]).trim().split('\n')[-1]
//         }
//     } catch (err) {
//         echo("Problem running elliott")
//         currentBuild.description += """
// ----------------------------------------
// ${err}
// ----------------------------------------"""
//         error("Could not process a find-builds command")
//     }
// }

// // Check that each of the RPM Diffs for the given advisory have been
// // resolved (waived/passed). RPM Diffs that require human intervention
// // will be collected and then later emailed out to the team.
// //
// // The job will block here until the diffs are resolved and someone
// // presses the `CONTINUE` button.
// //
// // @param <String> advisory: The ID of the advisory to check
// def signedComposeRpmdiffsResolved(advisory) {
//     def result = commonlib.shell(
//         script: "./rpmdiff.py check-resolved ${advisory}",
//         returnAll: true
//     )

//     if (result.returnStatus != 0) {
//         currentBuild.description += "\nRPM Diff resolution required"
//         mailForResolution(result.stdout)
//     }
// }

// // @param <String> err: Error message from failed command
// def mailForFailure(String err) {
//     def failureMessage = """Error creating new signed compose OpenShift ${params.BUILD_VERSION}

//   Errata Whitelist included advisories: ${errataList}
//   Jenkins Console Log: ${commonlib.buildURL('console')}

// ######################################################################
// ${err}
// ######################################################################

// """

//     echo("Mailing failure message: ")
//     echo(failureMessage)

//     commonlib.email(
//         // to: "aos-art-automation@redhat.com",
//         to: params.MAIL_LIST_FAILURE,
//         from: "aos-art-automation+failed-signed-compose@redhat.com",
//         replyTo: "aos-team-art@redhat.com",
//         subject: "Error creating new signed compose for OpenShift ${params.BUILD_VERSION} job #${currentBuild.number}",
//         body: failureMessage,
//     )
// }

// def analyzePuddleLogs(String dist='') {
//     dir(workdir) {
//         // Get the generic 'latest', it will tell us the actual name of this new puddle
//         commonlib.shell("wget ${puddleURL}${dist}/latest/logs/puddle.log -O puddle${dist}.log")
//         // This the tag of our newly created puddle
//         def latestTag = commonlib.shell(
//             script: "awk -n '/now points to/{print \$NF}' puddle${dist}.log",
//             returnStdout: true,
//         ).trim()

//         currentBuild.description += "\nTag${dist}: ${latestTag}"
//         // Form the canonical URL to our new puddle
//         def newPuddle = "${puddleURL}${dist}/${latestTag}"

//         currentBuild.description += "Puddle: ${newPuddle}"
//         // Save the changelog for emailing out
//         commonlib.shell("wget ${newPuddle}/logs/changelog.log -O changelog${dist}.log")

//         return [
//             changeLog: readFile("changelog${dist}.log"),
//             puddleLog: readFile("puddle${dist}.log"),
//             latestTag: latestTag,
//             newPuddle: newPuddle,
//         ]
//     }
// }

return this
