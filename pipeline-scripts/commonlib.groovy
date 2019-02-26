
ocpDefaultVersion = "4.0"
ocpVersions = [
    "4.1",
    "4.0",
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

def oseVersionParam(name='MINOR_VERSION') {
    return [
        name: name,
        description: 'OSE Version',
        $class: 'hudson.model.ChoiceParameterDefinition',
        choices: ocpVersions.join('\n'),
        defaultValue: ocpDefaultVersion,
    ]
}

def ocp4VersionParam(name='MINOR_VERSION') {
    return [
        name: name,
        description: 'OSE Version',
        $class: 'hudson.model.ChoiceParameterDefinition',
        choices: ocp4Versions.join('\n'),
        defaultValue: ocp4DefaultVersion,
    ]
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
