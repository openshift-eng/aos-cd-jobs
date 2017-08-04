
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

return this