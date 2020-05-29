slacklib = load("pipeline-scripts/slacklib.groovy")

ocp3Versions = [
    "3.11",
    "3.10",
    "3.9",
]

// All buildable versions of ocp4
ocp4Versions = [
    "4.6",
    "4.5",
    "4.4",
    "4.3",
    "4.2",
]

// Send UMB messages for these new nightlies, yields a list like:
//
//     [4-stable, 4.1.0-0.nightly, 4.2.0-0.nightly, 4.3.0-0.nightly, ...]
ocp4SendUMBVersions = ocp4Versions.collect(["4-stable"]) { it + ".0-0.nightly" }

// Which versions should undergo merges from origin->ose
ocpMergeVersions = [
    "4.5",
    "4.4",
    "4.3",
    "4.2",
    "3.11",
]

ocpVersions = ocp4Versions + ocp3Versions

/**
 * Why is ocp4ReleaseState needed?
 *
 * Before auto-signing, images were either built signed or unsigned.
 * Unsigned images were the norm and then, right before GA, we would rebuild
 * puddles and build as signed. In the new model, we always want to build
 * signed **if we plan on releasing the builds via an advisory**.
 *
 * There are a category of builds that we DON'T plan on releasing through
 * an advisory. For a brand new release stream (or new arch) in 4.x, we want
 * to build nightlies and make them available as pre-release builds so that
 * even the general public can start experimenting with the new features of the release.
 * These pre-release images contain RPMs which have traditionally been unsigned.
 *
 * We need them to continue to be unsigned!
 *
 * Any code we sign using the auto-signing facility should be passed through
 * the errata process / rpmdiff.
 *
 * Hence we need a very explicit source of truth on where our images are
 * destined. If it will ship via errata (state=release), we want to build signed. For
 * early access without an errata (state=pre-release).
 *
 * For extra complexity, different architectures in a release can be in
 * different release states. For example, s390x might still be pre-release
 * even after x86_64 is shipping for a given 4.x. While we could theoretically build the
 * x86_64 image with signed RPMs, and s390x images with unsigned RPMS, OSBS
 * prohibits this since it considers it an error.
 * TODO: ask osbs to make this a configurable option?
 *
 * Sooooo... when all arches are pre-release, we need to build unsigned. When any
 * arch is in release mode, we need to build all images with signed RPMs.
 *
 * Why is release map information not in doozer metadata. It could be.
 * 1) I think it would need some refactoring that won't be practical until
 *    the auto-signing work is validated.
 * 2) We normally initialize a new doozer group by copying an old one. This
 *    release state could easily be copied unintentionally.
 * 3) pre-release data is presently stored in poll-payload. This just tries
 *    to make it available for other jobs.
 *
 * Alternatively, maybe this becomes the source of truth and confusing aspects like
 * 'archOverrides' goes away in doozer config.
 */
ocp4ReleaseState = [
        "4.6": [
                'release': [],
                "pre-release": [ 'x86_64', 's390x', 'ppc64le' ],
        ],
        "4.5": [
            'release': [],
            "pre-release": [ 'x86_64', 's390x', 'ppc64le' ],
        ],
        "4.4": [
            "release": [ 'x86_64' ],
            "pre-release": ['s390x', 'ppc64le'],
        ],
        "4.3": [
            "release": [ 'x86_64', 's390x', 'ppc64le' ],
            "pre-release": [],
        ],
        "4.2": [
            "release": [ 'x86_64', 's390x' ],
            "pre-release": [],
        ],
        "4.1": [
            "release": [ 'x86_64' ],
            "pre-release": [],
        ]
]

ocpMajorVersions = [
    "4": ocp4Versions,
    "3": ocp3Versions,
    "all": ocpVersions,
]

ocpBaseImages = [
        "ansible.runner",
        "elasticsearch",
        "jboss.openjdk18.rhel7",
        "rhscl.nodejs.6.rhel7",
        "rhscl.nodejs.10.rhel7",
        "rhscl.nodejs.12.rhel7",
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


import java.util.concurrent.atomic.AtomicInteger
shellCounter = new AtomicInteger()

@NonCPS
def getNextShellCounter() {
    return shellCounter.incrementAndGet()
}

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
 * @param alwaysArchive true will always archive shell artifacts; default is to do so only on failure
 * @param returnAll true causes to return map with stderr, stdout, combined, and returnStatus
 * otherwise params are same as sh() step
 * @return same as sh() command, unless returnAll set
 * @throws error (unless returnAll or returnStatus set) with useful message (and archives)
 */
def shell(arg) {
    if (arg instanceof CharSequence) {  // https://stackoverflow.com/a/13880841
        arg = [script: arg]
    }
    arg = [:] + arg  // make a copy
    def alwaysArchive = arg.remove("alwaysArchive")
    def returnAll = arg.remove("returnAll")
    def script = arg.script  // keep a copy of original script
    def truncScript = (script.size() <= 75) ? script : script[0..35] + "..." + script[-36..-1]


    def threadShellIndex = getNextShellCounter()
    // put shell result files in a dir specific to this shell call, will symlink to generic "shell" for consistency.
    // in case we are running with changed dir, use absolute file paths.
    def shellDir = "${env.WORKSPACE}/shell.${currentBuild.number}"
    // use a subdir for each shell invocation
    def shellSubdir = "${env.WORKSPACE}/shell/sh.${threadShellIndex}." + truncScript.replaceAll( /[^\w-.]+/ , "_").take(80)

    // concurrency-safe creation of output dir and removal of any previous output dirs
    sh """#!/bin/bash +x
        mkdir -p ${shellDir}
        ln -sfn ${shellDir} ${env.WORKSPACE}/shell
        mkdir -p ${shellSubdir}
        find ${env.WORKSPACE} -maxdepth 1 -name 'shell.*' ! -name shell.${currentBuild.number} -exec rm -rf '{}' +
    """

    echo "Running shell script via commonlib.shell:\n${script}"
    def filebase = "${shellSubdir}/sh.${threadShellIndex}"
    arg.script =
    """#!/bin/bash +x
        set -euo pipefail
        # many thanks to https://stackoverflow.com/a/9113604
        {
            {
                {
                    ${script}
                }  2>&3 |  tee ${filebase}.out.txt   # redirect stderr to fd 3, capture stdout
            } 3>&1 1>&2 |  tee ${filebase}.err.txt   # turn captured stderr (3) into stdout and stdout>stderr
        }               |& tee ${filebase}.combo.txt # and then capture both (though maybe out of order)
    """

    // run it, capture rc, and don't error
    def rc = sh(arg + [returnStatus: true])
    if (rc || alwaysArchive) {
        writeFile file: "${filebase}.cmd.txt", text: script  // save cmd as context for archives
        // note that archival requires the location relative to workspace
        def relFilebase = filebase.minus("${env.WORKSPACE}/")
        safeArchiveArtifacts(["${relFilebase}.*"])
    }

    try {
        results = [
            stdout: readFile("${filebase}.out.txt"),
            stderr: readFile("${filebase}.err.txt"),
            combined: readFile("${filebase}.combo.txt"),
            returnStatus: rc,
        ]
    } catch(ex) {
        error("The following shell script is malformed and broke output capture:\n${script}")
    }

    if (arg.returnStatus) { return rc }  // like sh(returnStatus: true)
    if (returnAll) { return results }  // want results even if "failed"

    if (rc) {
        // raise error like sh() would but with context; trim message if long
        def output = results.combined.split("\n")
        if (output.size() > 5) {
            output = [ "[...see full archive #${threadShellIndex}...]" ] + array_to_list(output)[-5..-1]
        }
        error(  // TODO: use a custom exception class with attrs
"""\
failed shell command: ${truncScript}
with rc=${rc} and output:
${output.join("\n")}
""")
    }

    // successful, return like sh() would
    if (arg.returnStdout) { return results.stdout }
    return  // nothing
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

def inputRequired(slackOutput=null, cl) {
    if (!slackOutput) {
        slackOutput = slacklib.to(null)
    }
    def oldName = currentBuild.displayName
    try {
        currentBuild.displayName = "INPUT REQUIRED: ${oldName}"
        slackOutput.say('This job is waiting for input')
        cl()
    } finally {
        currentBuild.displayName = oldName
    }
}

def _retryWithOptions(goal, options, slackOutput=null, prompt='', cl) {
    def success = false
    if (!slackOutput) {
        slackOutput = slacklib.to(null)
    }
    while( !success ) {
        try {
            cl()
            success = true
        } catch ( retry_e ) {
            def description = "Problem encountered during: ${goal} => ${retry_e}"
            echo "${description}"
            slackOutput.failure("[INPUT REQUIRED] ${description}")
            inputRequired() {

                if ( ! prompt ) {
                    prompt = "Problem encountered during: ${goal}"
                }

                def resp = input message: prompt,
                        parameters: [
                                [
                                        $class     : 'hudson.model.ChoiceParameterDefinition',
                                        choices    : options.join('\n'),
                                        description : 'Retry this goal, Skip this goal, or Abort the pipeline',
                                        name       : 'action'
                                ]
                        ]

                def action = (resp instanceof String)?resp:resp.action

                echo "User selected: ${action}"
                slackOutput.say("User selected: ${action}")

                switch(action) {
                    case 'RETRY':
                        echo "User chose to retry"
                        break
                    case 'SKIP':
                        echo "User chose to skip."
                        success = true  // fake it
                        break
                    case 'ABORT':
                        error('User chose to abort retries of: ${goal}')
                }
            }
        }
    }
}

def retrySkipAbort(goal, slackOutput=null, prompt='', cl) {
    _retryWithOptions(goal, ['RETRY', 'SKIP', 'ABORT'], slackOutput, prompt, cl)
}

def retryAbort(goal, slackOutput=null, prompt='', cl) {
    _retryWithOptions(goal, ['RETRY', 'ABORT'], slackOutput, prompt, cl)
}

return this
