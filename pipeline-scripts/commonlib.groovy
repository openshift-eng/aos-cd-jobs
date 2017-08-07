
/**
 * Handles any common setup required by the library
 */
// https://issues.jenkins-ci.org/browse/JENKINS-33511
def initialize() {

    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }


    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
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