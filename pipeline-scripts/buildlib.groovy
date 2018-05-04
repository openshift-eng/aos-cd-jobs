
def commonlib = load("pipeline-scripts/commonlib.groovy")

commonlib.initialize()

GITHUB_URLS = [:]
GITHUB_BASE_PATHS = [:]

def initialize() {
    this.registry_login()
    this.path_setup()
    this.kinit()

    GITHUB_URLS = [:]
    GITHUB_BASE_PATHS = [:]
}

// Initialize $PATH and $GOPATH
def path_setup() {
    echo "Adding git managed script directories to PATH"

    GOPATH = "${env.WORKSPACE}/go"
    env.GOPATH = GOPATH
    sh "rm -rf ${GOPATH}"  // Remove any cruft
    sh "mkdir -p ${GOPATH}"
    echo "Initialized env.GOPATH: ${env.GOPATH}"
}

def kinit() {
    echo "Initializing ocp-build kerberos credentials"
    // Keytab for old os1 build machine
    // sh "kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM"
    sh "kinit -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM"
}

def registry_login() {
    // Login to new registry.ops to enable pushes
    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_registry.reg-aws',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'oc login -u $USERNAME -p $PASSWORD https://api.reg-aws.openshift.com'

        // Writing the file out is all to avoid displaying the token in the Jenkins console
        writeFile file:"docker_login.sh", text:'''#!/bin/bash
        docker login -u $USERNAME -p $(oc whoami -t) registry.reg-aws.openshift.com:443
        '''
        sh 'chmod +x docker_login.sh'
        sh './docker_login.sh'
    }
    // Login to quay.io
    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_registry.quay.io',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'docker login -u $USERNAME -p $PASSWORD quay.io'
    }
}

def print_tags(image_name) {
    // Writing the file out is all to avoid displaying the token in the Jenkins console
    writeFile file:"print_tags.sh", text:'''#!/bin/bash
    curl -sH "Authorization: Bearer $(oc whoami -t)" ''' + "https://registry.reg-aws.openshift.com/v2/${image_name}/tags/list | jq ."
    sh 'chmod +x print_tags.sh'
    sh './print_tags.sh'
}

def initialize_openshift_dir() {
    OPENSHIFT_DIR = "${GOPATH}/src/github.com/openshift"
    env.OPENSHIFT_DIR = OPENSHIFT_DIR
    sh "mkdir -p ${OPENSHIFT_DIR}"
    echo "Initialized env.OPENSHIFT_DIR: ${env.OPENSHIFT_DIR}"
}

def initialize_enterprise_images_dir() {
    this.initialize_openshift_dir()
    ENTERPRISE_IMAGES_DIR = "${env.WORKSPACE}/enterprise-images"
    sh "rm -rf ${ENTERPRISE_IMAGES_DIR}"  // Remove any cruft
    sh "mkdir -p ${ENTERPRISE_IMAGES_DIR}"
    OIT_PATH = "${ENTERPRISE_IMAGES_DIR}/tools/bin/oit"
    sh "git clone ${GITHUB_BASE}/enterprise-images.git ${ENTERPRISE_IMAGES_DIR}"
    env.ENTERPRISE_IMAGES_DIR = ENTERPRISE_IMAGES_DIR
    env.OIT_PATH = OIT_PATH
    echo "Initialized env.ENTERPRISE_IMAGES_DIR: ${env.ENTERPRISE_IMAGES_DIR}"
}

def oit(cmd, opts=[:]){
    cmd = cmd.replaceAll( '\n', ' ' ) // Allow newlines in command for readability, but don't let them flow into the sh
    cmd = cmd.replaceAll( ' \\ ', ' ' ) // If caller included line continuation characters, remove them
    return sh(
        returnStdout: opts.capture ?: false,
        script: "${env.ENTERPRISE_IMAGES_DIR}/tools/bin/oit --user=ocp-build --metadata-dir ${env.ENTERPRISE_IMAGES_DIR} ${cmd.trim()}")
}

def initialize_ose_dir() {
    this.initialize_openshift_dir()
    dir( OPENSHIFT_DIR ) {
        sh "git clone ${GITHUB_BASE}/ose.git"
        GITHUB_URLS["ose"] = "${GITHUB_BASE}/ose.git"
    }
    OSE_DIR = "${OPENSHIFT_DIR}/ose"
    GITHUB_BASE_PATHS["ose"] = OSE_DIR
    env.OSE_DIR = OSE_DIR
    echo "Initialized env.OSE_DIR: ${env.OSE_DIR}"
}

def initialize_origin_web_console_dir() {
    this.initialize_openshift_dir()
    dir( OPENSHIFT_DIR ) {
        sh "git clone ${GITHUB_BASE}/origin-web-console.git"
        GITHUB_URLS["origin-web-console"] = "${GITHUB_BASE}/origin-web-console.git"
    }
    WEB_CONSOLE_DIR = "${OPENSHIFT_DIR}/origin-web-console"
    GITHUB_BASE_PATHS["origin-web-console"] = WEB_CONSOLE_DIR
    env.WEB_CONSOLE_DIR = WEB_CONSOLE_DIR
    echo "Initialized env.WEB_CONSOLE_DIR: ${env.WEB_CONSOLE_DIR}"
}

def initialize_origin_web_console_server_dir() {
    this.initialize_openshift_dir()
    dir( OPENSHIFT_DIR ) {
        sh "git clone ${GITHUB_BASE}/origin-web-console-server.git"
        GITHUB_URLS["origin-web-console-server"] = "${GITHUB_BASE}/origin-web-console-server.git"
    }
    WEB_CONSOLE_SERVER_DIR = "${OPENSHIFT_DIR}/origin-web-console-server"
    GITHUB_BASE_PATHS["origin-web-console-server"] = WEB_CONSOLE_SERVER_DIR
    env.WEB_CONSOLE_SERVER_DIR = WEB_CONSOLE_SERVER_DIR
    echo "Initialized env.WEB_CONSOLE_SERVER_DIR: ${env.WEB_CONSOLE_SERVER_DIR}"
}

def initialize_openshift_ansible() {
    this.initialize_openshift_dir()
    dir( OPENSHIFT_DIR ) {
        sh "git clone ${GITHUB_BASE}/openshift-ansible.git"
        GITHUB_URLS["openshift-ansible"] = "${GITHUB_BASE}/openshift-ansible.git"
    }
    OPENSHIFT_ANSIBLE_DIR = "${OPENSHIFT_DIR}/openshift-ansible"
    GITHUB_BASE_PATHS["openshift-ansible"] = OPENSHIFT_ANSIBLE_DIR
    env.OPENSHIFT_ANSIBLE_DIR = OPENSHIFT_ANSIBLE_DIR
    echo "Initialized env.OPENSHIFT_ANSIBLE_DIR: ${env.OPENSHIFT_ANSIBLE_DIR}"
}

/**
 * Returns up to 100 lines of passed in spec content
 * @param spec_filename The spec filename to read
 * @return A string containing up to 100 lines of the spec's %changelog
 */
def read_changelog( spec_filename ) {
    def spec_content = readFile( spec_filename )
    def pos = spec_content.indexOf( "%changelog" )
    if ( pos > -1 ) {
        spec_content = spec_content.substring( pos + 10 ).trim()
    }
    lines = spec_content.split("\\r?\\n");

    def result = ""
    int i = 0
    for ( i = 0; i < 100 && i < lines.length; i++ ) {
        if ( lines[i].startsWith("%") ) { // changelog section has finished?
            break
        }
        result += "${lines[i]}\n"
    }

    if ( i == 100 ) {
        result += "....Truncated....\n"
    }

    return result
}

// Matcher is not serializable; use NonCPS
@NonCPS
def extract_rpm_version( spec_content ) {
    def ver_matcher = spec_content =~ /Version:\s*([.0-9]+)/
    if ( ! ver_matcher ) { // Groovy treats matcher as boolean in this context
        error( "Unable to extract Version field from RPM spec" )
    }
    return ver_matcher[0][1]
}

/**
 * Updates the Version: field in the specified rpm spec.
 * @param filename The filename of the .spec to alter
 * @param new_ver The new version to set
 */
def set_rpm_spec_version( filename, new_ver ) {
    echo "Setting Version in ${filename}: ${new_ver}"
    content = readFile( filename )
    content = content.replaceFirst( /(Version:\s*)([.0-9]+)/, "\$1${new_ver}" ) // \$1 is a backref to "Version:    "
    writeFile( file: filename, text: content )
}

// Matcher is not serializable; use NonCPS
@NonCPS
def extract_rpm_release_prefix(spec_content ) {
    def rel_matcher = spec_content =~ /Release:\s*([.a-zA-Z0-9+-]+)/  // Do not match vars like %{?dist}
    if ( ! rel_matcher ) { // Groovy treats matcher as boolean in this context
        error( "Unable to extract Release field from RPM spec" )
    }
    return rel_matcher[0][1]
}

/**
 * Updates the Release: field prefix in the specified rpm spec.
 * Variables following the prefix like %{?dist} will be left in place.
 * @param filename The filename of the .spec to alter
 * @param new_rel The new release prefix to set
 */
def set_rpm_spec_release_prefix( filename, new_rel ) {
    echo "Setting Release prefix in ${filename}: ${new_rel}"
    content = readFile( filename )
    content = content.replaceFirst( /(Release:\s*)([.a-zA-Z0-9+-]+)/, "\$1${new_rel}" ) // \$1 is a backref to "Release:    "
    writeFile( file: filename, text: content )
}

/**
 * Reads the specified RPM spec and parses version information from
 * it.
 * Sets SPEC_VERSION = "X.Y.Z..."
 * Sets SPEC_MAJOR_MINOR = "X.Y"
 * Sets SPEC_MAJOR = X   (int)
 * Sets SPEC_MINOR = Y   (int)
 * Sets SPEC_RELEASE = "0.03.330"   (release prefix before any %{?dist} variables)
 * @param filename The filename to read
 * @return Returns a spec object
 */
def read_spec_info(filename) {
    def spec_content = readFile(filename)
    v = this.extract_rpm_version( spec_content )
    def fields = v.tokenize('.')
    def major_minor = fields[0] + "." + fields[1]   // Turn "3.6.5" into "3.6"

    return [
            "version": v,
            "major_minor": major_minor,
            "major": fields[0].toInteger(),
            "minor": fields[1].toInteger(),
            "release": this.extract_rpm_release_prefix( spec_content ),
    ]
}

/**
 * Extracts ose (with origin as 'upstream') and:
 * Sets OSE_MASTER to major.minor ("X.Y") from current ose#master origin.spec
 * Sets OSE_MASTER_MAJOR to X
 * Sets OSE_MASTER_MINOR to Y
 * Sets OSE_MASTER_VERSION to "X.Y.Z..." from current ose#master
 * Sets OSE_MASTER_RELEASE to Release prefix from current ose#master origin.spec
 * Sets OSE_DIR to ose repo directory
 * @return Returns a spec object for the master branch
 */
def initialize_ose() {
    this.initialize_ose_dir()
    dir( OSE_DIR ) {
        sh "git remote add upstream ${GITHUB_BASE}/origin.git --no-tags"
        sh 'git fetch --all'
        spec = this.read_spec_info( "origin.spec" )

        // Perform some sanity checks

        if ( sh( returnStdout: true, script: "git ls-remote --heads ${GITHUB_BASE}/origin.git release-${spec.major_minor}" ).trim() != "" ) {
            error( "origin has a release branch for ${spec.major_minor}; ose should have a similar enterprise branch and ose#master's spec Version minor should be bumped" )
        }

        if ( sh( returnStdout: true, script: "git ls-remote --heads ${GITHUB_BASE}/openshift-ansible.git release-${spec.major_minor}" ).trim() != "" ) {
            error( "openshift-ansible has a release branch for ${spec.major_minor}; ose should have a similar enterprise branch and ose#master's spec Version minor should be bumped" )
        }

        // origin-web-console does not work like the other repos. It always has a enterprise branch for any release in origin#master.
        // origin-web-console#master contains changes for the latest origin-web-console#enterprise-X.Y which need to be be merged into
        // it when building X.Y.
        if ( sh( returnStdout: true, script: "git ls-remote --heads ${GITHUB_BASE}/origin-web-console.git enterprise-${spec.major_minor}" ).trim() == "" ) {
            error( "origin-web-console does not yet have an enterprise branch for ${spec.major_minor}; one should be created" )
        }

        env.OSE_MASTER_MAJOR_MINOR = OSE_MASTER_MAJOR_MINOR = spec.major_minor
        env.OSE_MASTER_MAJOR = OSE_MASTER_MAJOR = spec.major
        env.OSE_MASTER_MINOR = OSE_MASTER_MINOR = spec.minor
        env.OSE_MASTER_VERSION = OSE_MASTER_VERSION = spec.version
        env.OSE_MASTER_RELEASE = OSE_MASTER_RELEASE = spec.release
        return spec
    }
}

def initialize_origin_web_console() {
    this.initialize_origin_web_console_dir()
}

/**
 * Flattens a list of arguments into a string appropriate
 * for a bash script's arguments. Each argument will be
 * wrapped in '', so do not attempt to pass bash variables.
 * @param args The list of arguments to transform
 * @return A string containing the arguments
 */
@NonCPS
def args_to_string(Object... args) {
    def s = ""
    for ( def a : args ) {
        s += "'${a}' "
    }
    return s
}

/**
 * We need to execute some scripts directly from the rcm-guest host. To perform
 * those operations, we stream the script into stdin of an SSH bash invocation.
 * @param git_script_filename  The file in build-scripts/rcm-guest to execute
 * @param args A list of arguments to pass to script
 * @return Returns the stdout of the operation
 */
def invoke_on_rcm_guest(git_script_filename, Object... args ) {
    return sh(
            returnStdout: true,
            script: "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s ${this.args_to_string(args)} < ${env.WORKSPACE}/build-scripts/rcm-guest/${git_script_filename}",
    ).trim()
}

/**
 * Extract the puddle name from the puddle output
 * @param puddle_output The captured output of the puddle process
 * @return The puddle directory name (e.g. "2017-08-03.2" )
 */
// Matcher is not serializable; use NonCPS. Do not call CPS function (e.g. readFile from NonCPS methods; they just won't work)
@NonCPS
def extract_puddle_name(puddle_output ) {
    // Try to match a line like:
    // mash done in /mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/3.5/2017-08-07.1/mash/rhaos-3.5-rhel-7-candidate
    def matcher = puddle_output =~ /mash done in \/mnt\/rcm-guest\/puddles\/([\/a-zA-Z.0-9-]+)/
    split = matcher[0][1].tokenize("/")
    return split[ split.size() - 3 ]  // look three back and we should find puddle name
}

def build_puddle(conf_url, keys, Object...args) {
    echo "Building puddle: ${conf_url} with arguments: ${args}"
    if( keys != null ){
      echo "Using only signed RPMs with keys: ${keys}"
    }

    key_opt = (keys != null)?"--keys ${keys}":""

    // Ideally, we would call invoke_on_rcm_guest, but jenkins makes it absurd to invoke with conf_url as one of the arguments because the spread operator is not enabled.
    def puddle_output = sh(
            returnStdout: true,
            script: "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s -- --conf ${conf_url} ${key_opt} ${this.args_to_string(args)} < ${env.WORKSPACE}/build-scripts/rcm-guest/call_puddle.sh",
    ).trim()

    echo "Puddle output:\n${puddle_output}"
    def puddle_dir = this.extract_puddle_name( puddle_output )
    echo "Detected puddle directory: ${puddle_dir}"
    return puddle_dir
}

def build_ami(major, minor, version, release, yum_base_url, ansible_branch, mail_list) {
    if(major < 3 || (major == 3 && minor < 9))
        return
    final full_version = "${version}-${release}"
    final param = { type, name, value ->
        [$class: type + 'ParameterValue', name: name, value: value]
    }
    waitUntil {
        try {
            build(job: 'build%2Faws-ami', parameters: [
                param('String', 'OPENSHIFT_VERSION', version),
                param('String', 'OPENSHIFT_RELEASE', release),
                param('String', 'YUM_BASE_URL', yum_base_url),
                param('String', 'OPENSHIFT_ANSIBLE_CHECKOUT', ansible_branch),
                param('Boolean', 'USE_CRIO', true),
                param(
                    'String', 'CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE',
                    'registry.reg-aws.openshift.com:443/openshift3/cri-o:v'
                        + full_version)])
            return true
        } catch(err) {
            mail(
                to: "${mail_list}",
                from: "aos-cicd@redhat.com",
                subject: "RESUMABLE Error during AMI build for OCP v${full_version}",
                body: [
                    "Encountered an error: ${err}",
                    "Input URL: ${env.BUILD_URL}input",
                    "Jenkins job: ${env.BUILD_URL}"].join('\n'))
            final resp = input(
                message: "Error during AMI Build for OCP v${full_version}",
                parameters: [[
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    name: 'action',
                    choices: 'RETRY\nCONTINUE\nABORT',
                    description: [
                        'Retry (try the operation again).',
                        'Continue (fails are OK, continue pipeline).',
                        'Abort (terminate the pipeline).'].join(' ')]])
            if(resp == 'RETRY') {
                return false // cause waitUntil to loop again
            } else if(resp == 'CONTINUE') {
                echo 'User chose to continue. Build failures are non-fatal.'
                return true // terminate waitUntil
            } else { // ABORT
                error('User chose to abort pipeline because of ami build failures')
            }
        }
    }
}

def with_virtualenv(path, f) {
    final env = [
        "VIRTUAL_ENV=${path}",
        "PATH=${path}/bin:${env.PATH}",
        "PYTHON_HOME=",
    ]
    return withEnv(env, f)
}

// Parse record.log from OIT into a map
// Records will be formatted in a map like below:
// rpms/jenkins-slave-maven-rhel7-docker:
//   source_alias: jenkins
//   image: openshift3/jenkins-slave-maven-rhel7
//   dockerfile: /tmp/oit-uEeF2_.tmp/distgits/jenkins-slave-maven-rhel7-docker/Dockerfile
//   owners: ahaile@redhat.com,smunilla@redhat.com
//   distgit: rpms/jenkins-slave-maven-rhel7-docker]
// pms/aos-f5-router-docker:
//   source_alias: ose
//   image: openshift3/ose-f5-router
//   dockerfile: /tmp/oit-uEeF2_.tmp/distgits/aos-f5-router-docker/Dockerfile
//   owners:
//   distgit: rpms/aos-f5-router-docker
def parse_record_log( working_dir ) {
    def record = readFile( "${working_dir}/record.log" )
    lines = record.split("\\r?\\n");

    def result = [:]
    int i = 0
    int f = 0
    // loop records and pull type from first field
    // then create map all all remaining fields
    for ( i = 0; i < lines.size(); i++ ) {
        fields = lines[i].tokenize("|")
        type = fields[0]
        if(! result.containsKey(type)) {
            result[type] = []
        }
        record = [:]
        for ( f = 1; f < fields.size(); f++ ){
            entry = fields[f].tokenize("=")
            if ( entry.size() == 1 ){
                record[entry[0]] = null
            }
            else {
                record[entry[0]] = entry[1]
            }
        }
        result[type].add(record)
    }

    return result
}


// gets map of emails to notify from output of parse_record_log
// map formatted as below:
// rpms/jenkins-slave-maven-rhel7-docker
//   source_alias: jenkins
//   image: openshift3/jenkins-slave-maven-rhel7
//   dockerfile: /tmp/oit-uEeF2_.tmp/distgits/jenkins-slave-maven-rhel7-docker/Dockerfile
//   owners: bparees@redhat.com
//   distgit: rpms/jenkins-slave-maven-rhel7-docker
//   sha: 1b8903ef72878cd895b3f94bee1c6f5d60ce95c3
def get_distgit_notify( record_log ) {
    def result = [:]
    // It's possible there were no commits or no one specified to notify
    if ( ! record_log.containsKey("distgit_commit") || ! record_log.containsKey("dockerfile_notify")) {
        return result
    }

    commit = record_log["distgit_commit"]
    notify = record_log["dockerfile_notify"]

    int i = 0
    // get notification emails by distgit name
    for ( i = 0; i < notify.size(); i++ ) {
        result[notify[i]["distgit"]] = notify[i]
    }

    // match commit hash with notify email record
    for ( i = 0; i < commit.size(); i++ ) {
      if(result.containsKey(commit[i]["distgit"])){
        result[commit[i]["distgit"]]["sha"] = commit[i]["sha"]
      }
    }

    return result

}

def write_sources_file() {
  sources = """ose: ${env.OSE_DIR}
openshift-ansible: ${env.OPENSHIFT_ANSIBLE_DIR}
  """
  writeFile(file: "${env.WORKSPACE}/sources.yml", text: sources)
}

//https://stackoverflow.com/a/42775560
@NonCPS
List<List<?>> mapToList(Map map) {
  return map.collect { it ->
    [it.key, it.value]
  }
}

return this
