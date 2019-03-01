
ocp3DefaultVersion = "3.11"
ocp3Versions = [
    "3.11",
    "3.10",
    "3.9",
    "3.8",
    "3.7",
    "3.6",
    "3.5",
    "3.4",
    "3.3",
    "3.2",
    "3.1",
]

ocp4DefaultVersion = "4.0"
ocp4Versions = [
    "4.1",
    "4.0",
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

def safeArchiveArtifacts(List patterns) {
    for (pattern in patterns) {
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: pattern
        } catch (err) {
            echo "Failed to archive artifacts like ${pattern}: ${err}"
        }
    }
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



return this
