#!/usr/bin/groovy

commonlib = load("pipeline-scripts/commonlib.groovy")
commonlib.initialize()

GITHUB_URLS = [:]
GITHUB_BASE_PATHS = [:]

def initialize(test=false, checkMock=true) {
    if (checkMock) {
        commonlib.checkMock()
    }

    // don't bother logging into a registry or getting a krb5 ticket for tests
    if (!test) {
        this.registry_login()
        this.kinit()
    }
    this.path_setup()

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
    //
    // The '-f' ensures that the ticket is forwarded to remote hosts
    // when using SSH. This is required for when we build signed
    // puddles.
    sh "kinit -f -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM"
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

def registry_quay_dev_login() {
    // 2018-11-30 - Login to the
    // openshift-release-dev/ocp-v4.1-art-dev registry This is just
    // for test purposes right now

    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_dev_registry.quay.io',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'docker login -u "openshift-release-dev+art_quay_dev" -p $PASSWORD quay.io'
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

def cleanWhitespace(cmd) {
    return (cmd
        .replaceAll( ' *\\\n *', ' ' ) // If caller included line continuation characters, remove them
        .replaceAll( ' *\n *', ' ' ) // Allow newlines in command for readability, but don't let them flow into the sh
        .trim()
    )
}

def doozer(cmd, opts=[:]){
    return commonlib.shell(
        returnStdout: opts.capture ?: false,
        script: "doozer ${cleanWhitespace(cmd)}")
}

def elliott(cmd, opts=[:]){
    return commonlib.shell(
        returnStdout: opts.capture ?: false,
        script: "elliott ${cleanWhitespace(cmd)}")
}

def oc(cmd, opts=[:]){
    return commonlib.shell(
        returnStdout: opts.capture ?: false,
        script: "GOTRACEBACK=all /usr/bin/oc ${cleanWhitespace(cmd)}"
    )
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
 * Retrieve the branch list from a remote repository
 * @param repo_url a git@ repository URL.
 * @param pattern a matching pattern for the branch list. Only return matching branches
 *
 * @return a list of branch names.  Removes the leading ref path
 *
 * Requires SSH_AGENT to have set a key for access to the remote repository
 */
def get_branches(repo_url, pattern="") {

    branch_text = sh(
        returnStdout: true,
        script: [
            "git ls-remote ${repo_url} ${pattern}",
            "awk '{print \$2}'",
            "cut -d/ -f3"
        ].join(" | ")
    )

    return branch_text.split("\n")
}

/**
 * Retrieve a list of release numbers from the OCP remote repository
 * @param repo_url a git@ repository URL.
 * @return a list of OSE release numbers.
 *
 * Get the branch names beginning with 'enterprise-'.
 * Extract the release number string from each branch release name
 * Sort in version order (compare fields as integers, not strings)
 * Requires SSH_AGENT to have set a key for access to the remote repository
 */
def get_releases(repo_url) {
    // too clever: chain - get branch names, remove prefix, suffix
    r = get_branches(repo_url, "enterprise-*").collect { it - "enterprise-" }.findAll { it =~ /^\d+((\.\d+)*)$/ }

    // and sort
    z = sort_versions(r)
    return z
}

/**
 * Read an OAuth token from a file on the jenkins server.
 * Because groovy/jenkins sandbox won't let you read it without sh()
 * @param token_file - a file containing a single OAuth token string
 * @return - a string containing the OAuth token
 */
def read_oath_token(token_file) {
    token_string = sh (
        returnStdout: true,
        script: "cat ${token_file}"
    ).trim()
    return token_string
}

/**
 * Retrieve a single file from a Github repository
 * @param owner
 * @param repo_name
 * @param file_name
 * @param repo_token
 * @param branch
 * @return a string containing the contents of the specified file
 */
def get_single_file(owner, repo_name, file_name, repo_token, branch='master') {
    // Get a single file from a Github repository.

    auth_header = "Authorization: token " + repo_token
    file_url = "https://api.github.com/repos/${owner}/${repo_name}/contents/${file_name}?ref=${branch}"
    accept_header = "Accept: application/vnd.github.v3.raw"

    query = "curl --silent -H '${auth_header}' -H '${accept_header}' -L ${file_url}"
    content = sh(
	      returnStdout: true,
        script: query
    )

    return content
}

/**
 * Sort a list of dot separated version strings.
 * The sort function requires the NonCPS decorator.
 * @param v_in an unsorted array of version strings
 * @return a sorted array of version strings
 */
@NonCPS // because sorting in-line in Jenkins requires NonCPS all the way out
def sort_versions(v_in) {
    v_out = v_in.sort{a, b -> return cmp_version(a, b)}
}

/**
 * Compare two version strings
 * These are dot separated lists of numbers.  Each field is compared to the matching field numerically
 * @param v0 a version string
 * @param v1 a second version string
 * @return 0 if the versions are equal.  1 if v0 > v1, -1 if v0 < v1
 *
 * If two strings have different numbers of fields, the missing fields are padded with 0s
 * Two versions are equal if all fields are equal
 */
@NonCPS
def cmp_version(String v0, String v1) {
    // compare two version strings.
    // return:
    //   v0 < v1: -1
    //   v0 > v1:  1
    //   v0 = v1:  0

    // split both into arrays on dots (.)
    try {
        a0 = v0.tokenize('.').collect { it as int }
        a1 = v1.tokenize('.').collect { it as int }
    } catch (convert_error) {
        error("Invalid version strings: ${v0} or ${v1} - ${convert_error}")
    }

    // extend both to 3 fields with zeros if needed
    while (a0.size() < 3) { a0 << 0 }
    while (a1.size() < 3) { a1 << 0 }

    // zip these two together for comparison
    // major.minor.revision
    mmr = [a0, a1].transpose()

    // if any pair do not match, return the result
    for (field in mmr) {
        t = field[0].compareTo(field[1])
        if (t != 0) { return t }
    }
    return 0
}

/**
 * Test if two version strings are equivalent
 * @param v0 a dot separated version string
 * @param v1 a dot separated version string
 * @return true if versions are equal.  False otherwise
 *
 * If two strings have different numbers of fields, the missing fields are padded with 0s
 * Two versions are equal if all fields are equal
 */
@NonCPS
def eq_version(String v0, String v1) {
    // determine if two versions are the same
    // return:
    //   v0 == v1: true
    //   v0 != v1: false
    return cmp_version(v0, v1) == 0
}

/**
 * Determine the "build mode" based on the requested version, the version on HEAD of the master branch
 * and the versions found in the release branch list
 *
 * @param build_version a version string.  The version to be built
 * @param master_version a version string. The version on the master branch at HEAD
 * @param releases an array of version strings.  Each version string is from a release branch name
 * @return string the "build mode" to use when creating the local workspaces for OCP builds
 *
 * online:int: build from master
 * pre-release: build on release branch, merge master and upstream master before build
 * release: build from release branch
 *
 * NOTE: Must build either from master HEAD or an existing release branch. A build version which is not one of these
 * is invalid
 */
def auto_mode(build_version, master_version, releases) {
    // Conditions:
    //   BUILD_VERSION == master_version
    //   BUILD_VERSION in releases
    //
    //                |  BUILD_VERSION in releases
    // --------------------------------------------
    // build = master |   true      |   false     |
    // --------------------------------------------
    //      true      | pre-release |    online:int      |
    // -------------------------------------------
    //      false     |   release   |     X       |
    // -------------------------------------------
    // non-string map keys require parens during definition
    mode_table = [
        (true):  [ (true): "pre-release", (false): "online:int" ],
        (false): [ (true): "release",     (false): null  ]
    ]

    build_is_master = eq_version(build_version, master_version)
    build_has_release_branch = releases.contains(build_version)
    mode = mode_table[build_is_master][build_has_release_branch]

    if (mode == null) {
        error("""
invalid mode build != master and no release branch
  BUILD_VERSION: ${build_version}
  MASTER_VERSION: ${master_version}
  RELEASES: ${releases}
""")
    }
    return mode
}

/**
 * Create a new version string based on the build mode
 *
 * @param mode - The build mode string:
 *              ['online:int', 'online:stg', 'pre-release', 'release']
 * @param version_string - a dot separated <major>.<minor>.<release> string
 *               Where <major>, <minor>, and <release> are integer strings
 * @param release_string - same as the version string
 *
 * version_string and release_string are meant to mimic RPM version strings
 **/
@NonCPS
def new_version(mode, version_string, release_string) {

    // version and release are arrays of dot-seprated decimals
    version = version_string.tokenize('.').collect { it.toInteger() }
    release = release_string.tokenize('.').collect { it.toInteger() }

    // stage and int:
    //   version field is N.N.N unchanged
    //   release field is 0.I.S to differentiate builds
    //

    // pre-release and release:
    //
    //   version field is N.{N+1}
    //   release field is 1

    // pad release to 3 fields
    while (version.size() < 3) { version += 0 }
    while (release.size() < 3) { release += 0 }

    switch (mode) {
        case 'online:int':
            release[1]++
            release[2] = 0
            break
        case 'online:stg':
            release[2]++
            break
        case 'release':
        case 'pre-release':
            version[-1]++ // this puts a colon in the final field
            release = [1]
            break
    }

    return [
        'version': version.each{ it.toString() }.join('.'),
        'release': release.each{ it.toString() }.join('.')
    ]
}

/**
 * set the repo and branch information for each mode and build version
 * NOTE: here "origin" refers to the git reference, not to OpenShift Origin
 *
 * @param mode - a string indicating which branches to build from
 * @param build_version - a version string used to compose the branch names
 * @return a map containing the source origin and upstream branch names
 **/
def get_build_branches(mode, build_version) {

    switch(mode) {
        case "online:int":
            branch_names = ['origin': "master", 'upstream': "master"]
            break

        case "online:stg":
            branch_names = ['origin': "stage", 'upstream': "stage"]
            break

        case "pre-release":
            branch_names = ['origin': "enterprise-${build_version}", 'upstream': "release-${build_version}"]
            break

        case "release":
            branch_names = ['origin': "enterprise-${build_version}", 'upstream': null]
            break
    }

    return branch_names
}

/**
 * predicate: build with the web-server-console source tree?
 * @param version_string - a dot separated <major>.<minor>.<release> string
 *               Where <major>, <minor>, and <release> are integer strings
 * @return boolean
 **/
def use_web_console_server(version_string) {
    // the web console server was introduced with version 3.9
    return cmp_version(version_string, "3.9") >= 0
}

/**
 * set the merge driver for a git repo
 * @param repo_dir string - a git repository workspace
 * @param files List[String] - a list of file/dir strings for the merge driver
 **/
@NonCPS
def mock_merge_driver(repo_dir, files) {

    Dir(repo_dir) {
        sh "git config merge.ours.driver true"
    }

    // Use fake merge driver on specific packages
    gitattrs = new File(repo_dir + "/.gitattributes")
    files.each {
            gitattrs << "${it}  merge=ours\n"
    }
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

        // In the past this would perform some sanity checks based on the spec in master.
        // But 3.x has all the release branches it will ever have and 4.x branch policy
        // is changing, so 3.x no longer looks at master. Vars below are likely cruft that
        // needs to be carefully removed.

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

def invoke_on_use_mirror(git_script_filename, Object... args ) {
    return sh(
            returnStdout: true,
            script: "ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com sh -s ${this.args_to_string(args)} < ${env.WORKSPACE}/build-scripts/use-mirror/${git_script_filename}",
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

def param(type, name, value) {
    return [$class: type + 'ParameterValue', name: name, value: value]
}

def build_ami(major, minor, version, release, yum_base_url, ansible_branch, mail_list) {
    if(major < 3 || (major == 3 && minor < 9))
        return
    final full_version = "${version}-${release}"
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
    } catch(err) {
        commonlib.email(
            to: "${mail_list},jupierce@redhat.com,openshift-cr@redhat.com",
            from: "aos-cicd@redhat.com",
            subject: "RESUMABLE Error during AMI build for OCP v${full_version}",
            body: [
                "Encountered an error: ${err}",
                "Input URL: ${env.BUILD_URL}input",
                "Jenkins job: ${env.BUILD_URL}"
            ].join('\n')
        )

        // Continue on, this is not considered a fatal error
    }
}

/**
 * Trigger sweep job.
 *
 * @param String buildVersion: OCP build version (e.g. 4.2, 4.1, 3.11)
 * @param Boolean sweepBuilds: Enable/disable build sweeping
 */
def sweep(String buildVersion, Boolean sweepBuilds) {
    def sweepJob = build(
        job: 'build%2Fsweep',
        propagate: false,
        parameters: [
            string(name: 'BUILD_VERSION', value: buildVersion),
            booleanParam(name: 'SWEEP_BUILDS', value: sweepBuilds),
        ]
    )
    if (sweepJob.result != 'SUCCESS') {
        commonlib.email(
            replyTo: 'aos-art-team@redhat.com',
            to: 'aos-art-automation+failed-sweep@redhat.com',
            from: 'aos-art-automation@redhat.com',
            subject: "Problem sweeping after ${currentBuild.displayName}",
            body: "Jenkins console: ${commonlib.buildURL('console')}",
        )
        currentBuild.result = 'UNSTABLE'
    }
}

def sync_images(major, minor, mail_list, build_number) {
    // Run an image sync after a build. This will mirror content from
    // internal registries to quay. After a successful sync an image
    // stream is updated with the new tags and pullspecs.
    // Also update the app registry with operator manifests.
    // If builds don't succeed, email and set result to UNSTABLE.
    if(major < 4) {
        currentBuild.description = "Invalid sync request: Sync images only applies to 4.x+ builds"
        error(currentBuild.description)
    }
    def fullVersion = "${major}.${minor}"
    def results = []
    parallel "build-sync": {
        results.add build(job: 'build%2Fbuild-sync', propagate: false, parameters:
            [ param('String', 'BUILD_VERSION', fullVersion) ]  // https://stackoverflow.com/a/53735041
        )
    }, appregistry: {
        results.add build(job: 'build%2Fappregistry', propagate: false, parameters:
            [ param('String', 'BUILD_VERSION', fullVersion) ]  // https://stackoverflow.com/a/53735041
        )
    }
    if ( results.any { it.result != 'SUCCESS' } ) {
        commonlib.email(
            replyTo: mail_list,
            to: "aos-art-automation+failed-image-sync@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Problem syncing images after ${currentBuild.displayName}",
            body: "Jenkins console: ${commonlib.buildURL('console')}",
        )
        currentBuild.result = 'UNSTABLE'
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

// Parse record.log from Doozer into a map
// Records will be formatted in a map like below:
// rpms/jenkins-slave-maven-rhel7-docker:
//   source_alias: jenkins
//   image: openshift3/jenkins-slave-maven-rhel7
//   dockerfile: /tmp/doozer-uEeF2_.tmp/distgits/jenkins-slave-maven-rhel7-docker/Dockerfile
//   owners: ahaile@redhat.com,smunilla@redhat.com
//   distgit: rpms/jenkins-slave-maven-rhel7-docker]
// pms/aos-f5-router-docker:
//   source_alias: ose
//   image: openshift3/ose-f5-router
//   dockerfile: /tmp/doozer-uEeF2_.tmp/distgits/aos-f5-router-docker/Dockerfile
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
            // limit split to 2 in case value contains =
            entry = fields[f].split("=", 2)
            if ( entry.size() == 1 ){
                record[entry[0]] = null
            } else {
                record[entry[0]] = entry[1]
            }
        }
        result[type].add(record)
    }

    return result
}

// Find the supported arches for this release
//
// @param branch <String>: The name of the branch to get configs
//   for. For example: 'openshift-4.3'
//
// @return arches <List>: A list of the arches built for this branch
def branch_arches(String branch) {
    echo("Fetching group config for '${branch}'")
    def d = doozer("--group=${branch} config:read-group --yaml arches",
		   [capture: true]).trim()
    def datas = readYaml(text: d)
    return datas
}

// Search the build log for failed builds
def get_failed_builds(String log_dir, Boolean fullRecord=false) {
    record_log = parse_record_log(log_dir)
    this.get_failed_builds(record_log, fullRecord)
}

def get_failed_builds(Map record_log, Boolean fullRecord=false) {
    builds = record_log.get('build', [])
    failed_map = [:]
    for (i = 0; i < builds.size(); i++) {
        bld = builds[i]
        distgit = bld['distgit']
        if (bld['status'] != '0') {
            failed_map[distgit] = fullRecord ? bld : bld['task_url']
        } else if (bld['push_status'] != '0') {
            failed_map[distgit] = fullRecord ? bld : 'Failed to push built image. See debug.log'
        } else {
            // build may have succeeded later. If so, remove.
            failed_map.remove(distgit)
        }
    }

    return failed_map
}

// gets map of emails to notify from output of parse_record_log
// map formatted as below:
// rpms/jenkins-slave-maven-rhel7-docker
//   source_alias: [source_alias map]
//   image: openshift3/jenkins-slave-maven-rhel7
//   dockerfile: /tmp/doozer-uEeF2_.tmp/distgits/jenkins-slave-maven-rhel7-docker/Dockerfile
//   owners: bparees@redhat.com
//   distgit: rpms/jenkins-slave-maven-rhel7-docker
//   sha: 1b8903ef72878cd895b3f94bee1c6f5d60ce95c3    (NOT PRESENT ON FAILURE)
//   failure: ....error description....      (ONLY PRESENT ON FAILURE)
def get_distgit_notify( record_log ) {
    def result = [:]
    // It's possible there were no commits or no one specified to notify
    if ( ! record_log.containsKey("distgit_commit") || ! record_log.containsKey("dockerfile_notify")) {
        return result
    }

    source = record_log.get("source_alias", [])
    commit = record_log.get("distgit_commit", [])
    def failure = record_log.get("distgit_commit_failure", [])
    notify = record_log.get("dockerfile_notify", [])

    int i = 0
    def source_alias = [:]
    // will use source alias to look up where Dockerfile came from
    for ( i = 0; i < source.size(); i++ ) {
      source_alias[source[i]["alias"]] = source[i]
    }

    // get notification emails by distgit name
    for ( i = 0; i < notify.size(); i++ ) {
        notify[i].source_alias = source_alias.get(notify[i].source_alias, [:])
        result[notify[i]["distgit"]] = notify[i]
    }

    // match commit hash with notify email record
    for ( i = 0; i < commit.size(); i++ ) {
      if(result.containsKey(commit[i]["distgit"])){
        result[commit[i]["distgit"]]["sha"] = commit[i]["sha"]
      }
    }

    // OR see if the notification is for a merge failure
    for ( i = 0; i < failure.size(); i++ ) {
      if(result.containsKey(failure[i]["distgit"])){
        result[failure[i]["distgit"]]["failure"] = failure[i]["message"]
      }
    }

    return result
}

@NonCPS
def dockerfile_url_for(url, branch, sub_path) {
    if(!url || !branch) { return "" }

    // if it looks like an ssh github remote, transform it to https
    url = url.replaceFirst( /(?x) ^git@  ( [\w.-]+ ) : (.+) .git$/, "https://\$1/\$2" )

    return  "${url}/blob/${branch}/${sub_path ?: ''}"
}

def notify_dockerfile_reconciliations(doozerWorking, buildVersion) {
    // loop through all new commits that affect dockerfiles and notify their owners

    record_log = parse_record_log(doozerWorking)
    distgit_notify = get_distgit_notify(record_log)
    distgit_notify = mapToList(distgit_notify)

    for (i = 0; i < distgit_notify.size(); i++) {
        distgit = distgit_notify[i][0]
        val = distgit_notify[i][1]
        if (!val.owners) { continue }

        alias = val.source_alias
        url = dockerfile_url_for(alias.origin_url, alias.branch, val.source_dockerfile_subpath)
        dockerfile_url = url ? "Upstream source file: ${url}" : ""

        // Populate the introduction for all emails to owners
        explanation_body = """
Why am I receiving this?
------------------------
You are receiving this message because you are listed as an owner for an
OpenShift related image - or you recently made a modification to the definition
of such an image in github. Upstream (github) OpenShift Dockerfiles are
regularly pulled from their upstream source and used as an input to build our
productized images - RHEL-based OpenShift Container Platform (OCP) images.

To serve as an input to RHEL/OCP images, upstream Dockerfiles are
programmatically modified before they are checked into a downstream git
repository which houses all Red Hat images:
 - https://pkgs.devel.redhat.com/cgit/containers/

We call this programmatic modification "reconciliation" and you will receive an
email when the upstream Dockerfile changes so that you can review the
differences between the upstream & downstream Dockerfiles.
"""

        if ( val.failure) {
            email_subject = "FAILURE: Error reconciling Dockerfile for ${val.image} in OCP v${buildVersion}"
            explanation_body += """
What do I need to do?
---------------------
An error occurred during your reconciliation. Until this issue is addressed,
your upstream changes may not be reflected in the product build.

Please review the error message reported below to see if the issue is due to upstream
content. If it is not, the Automated Release Tooling (ART) team will engage to address
the issue. Please direct any questions to the ART team (#aos-art on slack).

Error Reported
--------------
${val.failure}

        """
        } else if ( val.sha ) {
            email_subject = "SUCCESS: Changed Dockerfile reconciled for ${val.image} in OCP v${buildVersion}"
            explanation_body += """
What do I need to do?
---------------------
You may want to look at the result of the reconciliation. Usually,
reconciliation is transparent and safe. However, you may be interested in any
changes being performed by the OCP build system.


What changed this time?
-----------------------
Reconciliation has just been performed for the image: ${val.image}
${dockerfile_url}
The reconciled (downstream OCP) Dockerfile can be viewed here:
 - https://pkgs.devel.redhat.com/cgit/${distgit}/tree/Dockerfile?id=${val.sha}

Please direct any questions to the Automated Release Tooling team (#aos-art on slack).
        """
        } else {
            error("Unable to determine notification reason; something is broken")
        }

        commonlib.email(
            to: val.owners,
            from: "aos-team-art@redhat.com",
            subject: email_subject,
            body: explanation_body);
    }
}

/**
 * send email to owners of failed image builds.
 * param failed_builds: map of records as below (all values strings):

presto:
    status: -1
    push_status: 0
    distgit: presto
    image: openshift/ose-presto
    owners: sd-operator-metering@redhat.com,czibolsk@redhat.com
    version: v4.0.6
    release: 1
    dir: doozer_working/distgits/containers/presto
    dockerfile: doozer_working/distgits/containers/presto/Dockerfile
    task_id: 20415814
    task_url: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=20415814
    message: "Exception occurred: ;;; Traceback (most recent call last): [...]"

 * param returnAddress: replies to the email will go to this
 * param defaultOwner: if no owner is listed, send build failure email to this
**/
def mail_build_failure_owners(failed_builds, returnAddress, defaultOwner) {
    List<Map> records = failed_builds.values()
    for(i = 0; i < records.size(); i++) {
        def failure = records[i]
        if (failure.status != '0') {
            def container_log = "doozer_working/brew-logs/${failure.distgit}/noarch-${failure.task_id}/container-build-x86_64.log"
            try {
                container_log = """
--------------------------------------------------------------------------
The following logs are just the container build portion of the OSBS build:
--------------------------------------------------------------------------
                \n""" + readFile(container_log)
            } catch(err) {
                echo "No container build log for failed ${failure.distgit} build\n" +
                     "(task url ${failure.task_url})\n" +
                     "at path ${container_log}"
                container_log = ""
            }
            commonlib.email(
                replyTo: returnAddress,
                from: "aos-art-automation@redhat.com",
                to: "aos-art-automation+failed-ocp-build@redhat.com,${failure.owners ?: defaultOwner}",
                subject: "Failed OCP build of ${failure.image}:${failure.version}",
                body: """
ART's brew/OSBS build of OCP image ${failure.image}:${failure.version} has failed.

${failure.owners
? "This email is addressed to the owner(s) of this image per ART's build configuration."
: "There is no owner listed for this build (you may want to add one)."
}

Builds may fail for many reasons, some under owner control, some under ART's
control, and some in the domain of other groups. This message is only sent when
the build fails consistently, so it is unlikely this failure will resolve
itself without intervention.

The brew build task ${failure.task_url}
failed with error message:
${failure.message}

ART's Jenkins build that resulted in this failure may be found at:
  * ${env.BUILD_URL}
The console log and artifacts there may assist in resolving this failure.
${container_log}
                """,
            )
        }
    }
}

@NonCPS
def determine_build_failure_ratio(record_log) {
    // determine what the last build status was for each distgit.
    // we're only interested in whether the build succeeded - ignore push failures.
    def last_status = [:]
    record_log.get('build', []).each { record -> last_status[record.distgit] = record.status }

    def total = last_status.size()
    def failed = last_status.values().count { it != '0' }
    def ratio = total ? failed / total : 0

    return [failed: failed, total: total, ratio: ratio]
}

def write_sources_file() {
  sources = """ose: ${env.OSE_DIR}
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

def watch_brew_task_and_retry(name, taskId, brewUrl) {
    // Watch brew task to make sure it succeeds. If it fails, retry twice before giving up.
    try {
        commonlib.shell "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew watch-task ${taskId}"
    } catch (err) {
        msg = "Error in ${name} build task: ${err}\nSee failed brew task ${brewUrl}"
        echo msg
        try {
            retry(2) {
		sleep(120)  // brew state takes time to settle, so wait to retry
                commonlib.shell "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew resubmit ${taskId}"
            }
        } catch (err2) {
            echo "giving up on ${name} build after three failures"
            error(msg)
        }
    }
}

def getGroupBranch(doozerOpts) {
    // for given doozer options determine the distgit branch from the group.yml file
    def branch = doozer("${doozerOpts} config:read-group branch", [capture: true]).trim()
    if (branch == "" ) {
        error("failed to read branch from group.yml")
    } else if (branch.contains("\n")) {
        error("reading branch from group.yml got multiple lines:\n${branch}")
    }
    return branch
}

def cleanWorkdir(workdir) {
    // get a fresh workdir; removing the old one is left in the background.
    // NOTE: if wrapped in commonlib.shell, this would wait for the background process;
    // this is designed to run instantly and never fail, so just run it in a normal shell.
    sh """
        mkdir -p ${workdir}
        mv ${workdir} ${workdir}.rm.${currentBuild.number}
        mkdir -p ${workdir}
        # see discussion at https://stackoverflow.com/a/37161006 re:
        JENKINS_NODE_COOKIE=dontKill BUILD_ID=dontKill nohup bash -c 'rm -rf ${workdir}.rm.*' &
    """
}

def latestOpenshiftRpmBuild(stream, branch) {
    pkg = stream.startsWith("3") ? "atomic-openshift" : "openshift"
    retry(3) {
        commonlib.shell(
            script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew latest-build --quiet ${branch}-candidate ${pkg} | awk '{print \$1}'",
            returnStdout: true,
        ).trim()
    }
}

def defaultReleaseFor(stream) {
    return stream.startsWith("3") ? "1" : new Date().format("yyyyMMddHHmm")
}

// From a brew NVR of openshift, return just the V part.
@NonCPS  // unserializable regex not allowed in combination with pipeline steps (error|echo)
def extractBuildVersion(build) {
    def match = build =~ /(?x) openshift- (  \d+  ( \. \d+ )+  )-/
    return match ? match[0][1] : "" // first group in the regex
}

/**
 * Given build parameters, determine the version for this build.
 * @param stream: OCP minor version "X.Y"
 * @param stream: distgit branch "rhaos-X.Y-rhel-[78]"
 * @param versionParam: a version "X.Y.Z", empty to reuse latest version, "+" to increment latest .Z
 * @return the version determined "X.Y.Z"
 */
def determineBuildVersion(stream, branch, versionParam) {
    def version = "${stream}.0"  // default

    def prevBuild = latestOpenshiftRpmBuild(stream, branch)
    if(versionParam == "+") {
        // increment previous build version
        version = extractBuildVersion(prevBuild)
        if (!version) { error("Could not determine version from last build '${prevBuild}'") }

        def segments = version.tokenize(".").collect { it.toInteger() }
        segments[-1]++
        version = segments.join(".")
        echo("Using version ${version} incremented from latest openshift package ${prevBuild}")
    } else if(versionParam) {
        // explicit version given
        version = commonlib.standardVersion(versionParam, false)
        echo("Using parameter for build version: ${version}")
    } else if (prevBuild) {
        // use version from previous build
        version = extractBuildVersion(prevBuild)
        if (!version) { error("Could not determine version from last build '${prevBuild}'") }
        echo("Using version ${version} from latest openshift package ${prevBuild}")
    }

    if (! version.startsWith("${stream}.")) {
        // The version we came up with somehow doesn't match what we expect to build; abort
        error("Determined a version, '${version}', that does not begin with '${stream}.'")
    }

    return version
}

@NonCPS
String extractAdvisoryId(String elliottOut) {
    def matches = (elliottOut =~ /https:\/\/errata\.devel\.redhat\.com\/advisory\/([0-9]+)/)
    matches[0][1]
}

@NonCPS
String extractBugId(String bugzillaOut) {
    def matches = (bugzillaOut =~ /#([0-9]+)/)
    matches[0][1]
}

/**
 * Checks the status of the freeze_automation key in the group.yml and
 * returns whether the current run is permitted accordingly.
 * @param doozerOpts A string containing, at least, a `--group` parameter.
 */
def isBuildPermitted(doozerOpts) {
    // check whether the group should be built right now
    def freeze_automation = doozer("${doozerOpts} config:read-group --default 'no' freeze_automation",
                                   [capture: true]).trim()

    def builderEmail
    wrap([$class: 'BuildUser']) {
        builderEmail = env.BUILD_USER_EMAIL
    }

    echo "Group's freeze_automation flag: ${freeze_automation}"
    echo "Builder email: ${builderEmail}"

    if (freeze_automation == "yes") {
        echo "All automation is currently disabled by freeze_automation in group.yml."
        return false
    }

    if (freeze_automation == "scheduled" && builderEmail == null) {
        echo "Only manual runs are permitted according to freeze_automation in group.yml and this run appears to be non-manual."
        return false
    }

    return true
}

/**
 * Throws an exception if isBuildPermitted(...) returns false.
 * @param doozerOpts A string containing, at least, a `--group` parameter.
 */
def assertBuildPermitted(doozerOpts) {
    if (!isBuildPermitted(doozerOpts)) {
        currentBuild.result = 'UNSTABLE'
        currentBuild.description = 'Builds not permitted'
        error('This build is being terminated because it is not permitted according to current group.yml')
    }
}

/**
 * Run elliott find-builds and attach to given advisory.
 * It looks for builds twice (rhel-7 and rhel-8) for OCP 4.y
 * Side-effect: Advisory states are changed to "NEW FILES" in order to attach builds.
 *
 * @param String[] kinds: List of build kinds you want to find (e.g. ["rpm", "image"])
 * @param String buildVersion: OCP build version (e.g. 4.2, 4.1, 3.11)
 */
def attachBuildsToAdvisory(kinds, buildVersion) {
    def groupOpt = "-g openshift-${buildVersion}"

    try {
        if ("rpm" in kinds) {
            elliott("${groupOpt} change-state -s NEW_FILES --use-default-advisory rpm")
            elliott("${groupOpt} find-builds -k rpm --use-default-advisory rpm")
        }
        if ("image" in kinds) {
            elliott("${groupOpt} change-state -s NEW_FILES --use-default-advisory image")
            elliott("${groupOpt} find-builds -k image --use-default-advisory image")
        }
    } catch (err) {
        currentBuild.description += "ERROR: ${err}"
        error("elliott find-builds failed: ${err}")
    }
}


/**
 * Scans data outputted by config:scan-sources yaml and records changed
 * elements in the object it returns which has a .rpms list and an .images list.
 * The lists are empty if no change was detected.
 */
@NonCPS
def getChanges(yamlData) {
    def changed = ["rpms": [], "images": []]
    changed.each { kind, list ->
        yamlData[kind].each {
            if (it["changed"]) {
                list.add(it["name"])
            }
        }
    }
    return changed
}

return this
