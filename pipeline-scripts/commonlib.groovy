ocp3DefaultVersion = "3.11"
ocp3Versions = [
    "3.11",
    "3.10",
    "3.9",
]

// Which version of ocp4 build parameters should show by default
ocp4DefaultVersion = "4.4"

// All buildable versions of ocp4
ocp4Versions = [
    "4.5",
    "4.4",
    "4.3",
    "4.2",
    "4.1",
]

// Which versions should undergo merges from origin->ose
ocpMergeVersions = [
    "4.5",
    "4.4",
    "4.3",
    "4.2",
    "4.1",
    "3.11",
]

ocpDefaultVersion = ocp4DefaultVersion
ocpVersions = ocp4Versions + ocp3Versions

ocpMajorVersions = [
    "4": ocp4Versions,
    "3": ocp3Versions,
    "all": ocpVersions,
]
ocpMajorDefaultVersion = [
    "4": ocp4DefaultVersion,
    "3": ocp3DefaultVersion,
    "all": ocp4DefaultVersion,
]

ocpBaseImages = [
        "ansible.runner",
        "elasticsearch",
        "jboss.openjdk18.rhel7",
        "rhscl.nodejs.6.rhel7",
        "rhel7",
        "ubi7",
        "ubi8",
]

/**
 * Handles any common setup required by the library
 */
def initialize() {
    // https://issues.jenkins-ci.org/browse/JENKINS-33511 no longer appears relevant
}

def checkMock() {
    // User can have the job end if this is just a run to pick up parameter changes
    // (which Jenkins discovers by running the job).
    if (env.MOCK == null || MOCK.toBoolean()) {
        currentBuild.displayName = "#${currentBuild.number} - update parameters"
        currentBuild.description = "Ran in mock mode"
        error( "Ran in mock mode to pick up any new parameters" )
    }
}

def mockParam() {
    return [
        name: 'MOCK',
        description: 'Pick up changed job parameters and then exit',
        $class: 'BooleanParameterDefinition',
        defaultValue: false
    ]
}

def ocpVersionParam(name='MINOR_VERSION', majorVersion='all') {
    return [
        name: name,
        description: 'OSE Version',
        $class: 'hudson.model.ChoiceParameterDefinition',
        choices: ocpMajorVersions[majorVersion].join('\n'),
        defaultValue: ocpMajorDefaultVersion[majorVersion],
    ]
}

def suppressEmailParam() {
    return [
        name: 'SUPPRESS_EMAIL',
        description: 'Do not actually send email, just archive it',
        $class: 'BooleanParameterDefinition',
        defaultValue: !env.JOB_NAME.startsWith("aos-cd-builds/"),
    ]
}

/**
 * Normalize input so whether the user supplies "v" or not we get what we want.
 * Also, for totally bogus versions we get an error early on.
 */
def standardVersion(String version, Boolean withV=true) {
    version = version.trim()
    def match = version =~ /(?ix) ^v? (  \d+ (\.\d+)+  )$/
    if (!match) {
        error("Not a valid version: ${version}")
    }
    version = match[0][1] // first group in the regex
    return withV ? "v${version}" : version
}

def cleanCommaList(str) {
    // turn a list separated by commas or spaces into a comma-separated list
    str = (str == null) ? "" : str
    return str.replaceAll(',', ' ').split().join(',')
}

// A reusable way to generate a working build URL. Translates it into
// localhost for us. Then later when we get rid of that localhost
// thing we'll be able to undo this all at once. This can be directly
// used in strings. See EXAMPLES below.
//
// @param append: OPTIONAL: Location to append to the end. No '/'s
// required. For reference, here are some common ones you might use:
//
// * console - Go to the console log
// * input - Go to any pending input prompts
//
// EXAMPLES:
//
// Assign to a variable the build url or the user input page:
//     def buildURL = commonlib.buildURL()
//     def buildURL = commonlib.buildURL('input')
//
// Simply print it out:
//     echo("Jenkins job: ${commonlib.buildURL()}")
//
// Use it in an email:
//   commonlib.email(
//       to: params.MAIL_LIST_INPUT,
//       from: "aos-art-automation+input-required@redhat.com",
//       replyTo: "aos-team-art@redhat.com",
//       subject: "Input required for job ${currentBuild.number}",
//       body: """
//         Job requires input to continue:
//           Jenkins Input: ${commonlib.buildURL('input')}
//   """)
def buildURL(String append='') {
    env.BUILD_URL.replace('https://buildvm.openshift.eng.bos.redhat.com:8443', 'https://localhost:8888') + append
}

emailIndex = 0
/**
 * Wrapper to persist email as an artifact and enable suppressing actual email
 */
def email(args) {
    args.body += """
------------------------------------------------------

NOTE: These job links are only available to ART. Please contact us if
you need to see something specific from the logs.

Jenkins Job: ${buildURL()}
Console Log: ${buildURL('console')}
"""
    if (params.SUPPRESS_EMAIL) {
        def title = currentBuild.displayName ?: ""
        if (!title.contains("no email")) {
            currentBuild.displayName = "${title} [no email]"
        }
    } else {
        try {
            mail(args)
        } catch (err) { // don't usually want to fail the job for this
            echo "Failure sending email: ${err}"
        }
    }

    // now write this out and archive it
    try {
        // make a clean space for files
        if (emailIndex == 0) {
            sh("rm -rf email")
            sh("mkdir -p email")
        }

        // create a sanitized but recognizable name
        to = args.to ?: args.cc ?: args.bcc ?: "NOBODY"
        to = to.replaceAll(/[^@.\w]+/, "_")
        subject = args.get("subject", "NO SUBJECT").replaceAll(/\W+/, "_")
        filename = String.format("email/email%03d-%s-%s.txt", ++emailIndex, to, subject)

        // this is a bit silly but writeYaml and writeFile lack finesse
        body = args.remove("body")  // unreadable when written as yaml
        writeYaml file: filename, data: args
        yaml = readFile filename
        writeFile file: filename, text: yaml + "\n\n" + body
        this.safeArchiveArtifacts([filename])
    } catch (err) {
        echo "Failure writing and archiving email file:\n${err}"
    }
}

def safeArchiveArtifacts(List patterns) {
    for (pattern in patterns) {
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: pattern
        } catch (err) {
            echo "Failed to archive artifacts like ${pattern}: ${err}"
        }
    }
}

shellIndex = 0
/**
 * Wraps the Jenkins Pipeline sh step in order to get actually useful exceptions.
 * Because https://issues.jenkins-ci.org/browse/JENKINS-44930 is ridiculous.
 *
 * N.B. the returnStatus value is wrong. It's not because of the bash wrapper,
 * which propagates the correct rc fine if run outside Jenkins. Presumably it's
 * Jenkins being screwy. It does at least return an rc with the same truthiness
 * (0 for success, 1 for failure).
 * If your code really cares about the rc being right then do not use.
 *
 * @param returnAll true causes to return map with stderr, stdout, combined, and returnStatus
 * @param otherwise same as sh() command
 * @return same as sh() command, unless returnAll set
 * @throws error (unless returnAll or returnStatus set) with useful message (and archives)
 */
def shell(arg) {
    if (arg instanceof CharSequence) {  // https://stackoverflow.com/a/13880841
        arg = [script: arg]
    }
    arg = [:] + arg  // make a copy
    def returnAll = arg.remove("returnAll")
    def script = arg.script  // keep a copy of original script
    def truncScript = (script.size() <= 75) ? script : script[0..35] + "..." + script[-36..-1]

    // ensure a clean space to save output files
    if (!shellIndex++) { sh("rm -rf shell") }

    def filename = "shell/sh.${shellIndex}." + truncScript.replaceAll( /[^\w-.]+/ , "_").take(80)
    sh("mkdir -p ${filename}")
    filename += "/sh.${shellIndex}"

    echo "Running shell script via commonlib.shell:\n${script}"
    arg.script =
    """
        set +x
        set -euo pipefail
        # many thanks to https://stackoverflow.com/a/9113604
        {
            {
                {
                    ${script}
                }  2>&3 |  tee ${filename}.out.txt   # redirect stderr to fd 3, capture stdout
            } 3>&1 1>&2 |  tee ${filename}.err.txt   # turn captured stderr (3) into stdout and stdout>stderr
        }               |& tee ${filename}.combo.txt # and then capture both (though maybe out of order)
    """

    // run it, capture rc, and don't error
    def rc = sh(arg + [returnStatus: true])

    if (returnAll) {
        return [
            stdout: readFile("${filename}.out.txt"),
            stderr: readFile("${filename}.err.txt"),
            combined: readFile("${filename}.combo.txt"),
            returnStatus: rc,
        ]
    }
    if (arg.returnStatus) { return rc } // same as sh() so why bother?
    if (arg.returnStdout && rc == 0) { return readFile("${filename}.out.txt")}
    if (rc) {
        // error like sh() would but with useful content. and archive it.
        writeFile file: "${filename}.cmd.txt", text: script  // context for archive
        safeArchiveArtifacts(["${filename}.*"])
        def output = readFile("${filename}.combo.txt").split("\n")

        // want the error message to be user-directed, so trim it a bit
        if (output.size() > 5) {
            output = [ "[...see full archive #${shellIndex}...]" ] + array_to_list(output)[-5..-1]
        }
        error(  // TODO: use a custom exception class with attrs
"""\
failed shell command: ${truncScript}
with rc=${rc} and output:
${output.join("\n")}
""")
    }

    return  // nothing, like normal sh()
}

/**
 * Jenkins doesn't seems to whitelist .asList(),
 * so this is an awful workaround.
 * @param array An array
 * @return Returns a list containing the elements of the array
 */
@NonCPS
def array_to_list(array) {
    l = []
    for ( def e : array ) {
        l << e
    }
    return l
}

/**
 * Given a version string x.y.z,
 * returns the x.y part.
 * e.g. "4.1.0-rc.9" => "4.1"
 */
String extractMajorMinorVersion(String version) {
    return (version =~ /^(\d+\.\d+)/)[0][1]
}

/**
 * Returns the major and minor version numbers for a given version string.
 * e.g. "4.1.0-rc.9" => [4, 1]
 */
def extractMajorMinorVersionNumbers(String version) {
    return (version =~ /^(\d+)\.(\d+)/)[0].subList(1,3).collect { it as int }
}

/**
    Returns the architecture name extracted from a release name.
    Only known architecture names are recognized, defaulting to `defaultArch`.
    e.g.
        "4.4.0-0.nightly-ppc64le-2019-11-06-041852" => "ppc64le"
        "4.4.0-0.nightly-s390x-2019-11-06-041852" => "s390x"
        "4.4.0-0.nightly-2019-11-06-041852" => "x86_64"
*/
def extractArchFromReleaseName(String release, String defaultArch='x86_64') {
    return (release =~ /(x86_64|ppc64le|s390x)?$/)[0][1] ?: defaultArch
}

/**
 * Attempts, for a specified duration, to claim a Jenkins lock. If claimed, the
 * lock is released before returning. Callers should be aware this leaves
 * a race condition and there is no guarantee they will get the lock themselves. Thus, this
 * method should only be used for optimization decisions and not relied on for
 * guaranteed behavior.
 * @param lockName The name of the lock to test
 * @param timeout_seconds The number of seconds to try to acquire the lock before giving up
 * @return Returns true if the lock was successfully able to be claimed.
 */
def canLock(lockName, timeout_seconds=10) {
    def claimed = false
    try {
        timeout(time: timeout_seconds, unit: 'SECONDS') {
            lock(lockName) {
                claimed = true
            }
        }
    } catch ( e ) {
        echo "Timeout waiting for lock ${lockName}"
    }
    return claimed
}

/**
 * Each OCP architecture gets its own release controller. They are hosted
 * on different routes. This method returns a URL based on the name of the
 * release stream you want to query.
 * @param releaseStreamName - e.g. 4-stable or 4-stable-s390x
 * @return Returns something like "https://openshift-release-s390x.svc.ci.openshift.org"
 */
def getReleaseControllerURL(releaseStreamName) {
    def archSuffix = ''
    def streamNameComponents = releaseStreamName.split('-') // e.g. ['4', 'stable', 's390x']  or [ '4', 'stable' ]
    if ('s390x' in streamNameComponents) {
        archSuffix = "-s390x" // e.g. -s390x
    } else if ('ppc64le' in streamNameComponents) {
        archSuffix = "-ppc64le"
    }
    return "https://openshift-release${archSuffix}.svc.ci.openshift.org"
}

return this
