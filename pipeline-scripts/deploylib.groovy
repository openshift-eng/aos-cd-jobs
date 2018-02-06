
def commonlib = load("pipeline-scripts/commonlib.groovy")

commonlib.initialize()

/**
 * Converts a line delimited string to a map. Each
 * line should be empty or contain key=value.
 * @param s The lines process
 * @return A map containing each key value pair
 */
@NonCPS
def lines_to_map(s) {
    def m = [:]

    if ( s == null ) {
        return m
    }

    s.eachLine {
        def line = it.trim()
        if ( line != "" ) {
            def tokens = line.tokenize("=")
            def k = tokens[0]
            def v = tokens.size()>1?tokens[1]:""
            m[ k ]= v
        }
    }
    return m
}

def initialize(cluster_spec, opts_string="") {
    // clusters specifications are of the form group:env:cluster_name
    parts = cluster_spec.split(":")
    CLUSTER_GROUP = parts[0] // e.g. starter vs dedicated
    CLUSTER_ENV = parts[1] // e.g. int vs stg
    CLUSTER_NAME = parts[2]
    SHARED_OPERATION_OPTS = lines_to_map(opts_string)
}

/**
 * Iterates through a map and flattens it into -e key1=value1 -e key2=value2...
 * Appropriate for passing in as tower operation
 * @param map The map to process
 * @return A string of flattened key value properties
 */
@NonCPS // .each has non-serializable aspects, so use NonCPS
def map_to_string(map) {
    def s = ""

    if ( map == null ) {
        return s
    }

    map.each{ k, v -> s += "-e ${k}=${v} " }
    return s
}

def run( operation_name, opts = [:], capture_stdout=false, interactive_retry=true ) {

    if ( opts == null ) {
        opts = [:]
    }
    // Add shared opts to operation specific options
    opts << SHARED_OPERATION_OPTS

    echo "\n\nRunning operation: ${operation_name} with options: ${opts}"
    echo "-------------------------------------------------------"

    output = ""
    waitUntil {
        try {
            // -t is necessary for cicd-control.sh to be terminated by Jenkins job terminating ssh early: https://superuser.com/questions/20679/why-does-my-remote-process-still-run-after-killing-an-ssh-session
            cmd = "ssh -t -o StrictHostKeyChecking=no opsmedic@use-tower2.ops.rhcloud.com -- -d ${CLUSTER_GROUP} -c ${CLUSTER_NAME} -o ${operation_name} ${this.map_to_string(opts)}"
            ansiColor('xterm') {
                output = sh(
                        returnStdout: capture_stdout,
                        script: cmd
                )
            }
            return true // finish waitUntil
        } catch ( rerr ) {

            if ( ! interactive_retry ) {
                throw rerr
            }

            try {
                mail(to: "${MAIL_LIST_FAILURE}",
                        from: "aos-cd@redhat.com",
                        subject: "RESUMABLE Error during ${operation_name} on cluster ${CLUSTER_NAME}",
                        body: """Encountered an error: ${rerr}

Input URL: ${env.BUILD_URL}input

Jenkins job: ${env.BUILD_URL}
""");
            } catch ( mail_exception ) {
                echo "One or more errors sending email: ${mail_exception}"
            }

            def resp = input    message: "On ${CLUSTER_NAME}: Error during ${operation_name} with args: ${opts}",
                                parameters: [
                                                [$class: 'hudson.model.ChoiceParameterDefinition',
                                                 choices: "RETRY\nSKIP\nABORT",
                                                 description: 'Retry (try the operation again). Skip (skip the operation without error). Abort (terminate the pipeline).',
                                                 name: 'action']
                                ]

            if ( resp == "RETRY" ) {
                return false  // cause waitUntil to loop again
            } else if ( resp == "SKIP" ) {
                echo "User chose to skip operation: ${operation_name}"
                output = "" //
                return true // Terminate waitUntil
            } else { // ABORT
                error( "User chose to abort job because of error with: ${operation_name}" )
            }
        }
    }

    if ( capture_stdout ) {
        echo "${output}"
        output = output.trim()
    } else {
        output = "capture_stdout=${capture_stdout}"
    }

    echo "-------------------------------------------------------\n\n"

    return output
}

return this
