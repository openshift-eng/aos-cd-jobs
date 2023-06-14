#!/usr/bin/groovy
import java.net.URLEncoder

commonlib = load("pipeline-scripts/commonlib.groovy")
commonlib.initialize()
slacklib = commonlib.slacklib

GITHUB_URLS = [:]
GITHUB_BASE_PATHS = [:]
GITHUB_BASE = "git@github.com:openshift"

def initialize(test=false, regAws=false) {
    this.proxy_setup()
    this.setup_venv(true)
    this.path_setup()

    // don't bother logging into a registry or getting a krb5 ticket for tests
    if (!test) {
        this.kinit()
        if (regAws) {
            this.registry_login()
        }
    }
}

// Ensure that calls to "oc" within the passed in block will interact with
// app.ci as art-publish service account.
def withAppCiAsArtPublish(closure) {
    withCredentials([file(credentialsId: 'art-publish.app.ci.kubeconfig', variable: 'KUBECONFIG')]) {
        closure()
    }
}

// Initialize $PATH and $GOPATH
def path_setup() {
    echo "Adding git managed script directories to PATH"

    GOPATH = "${env.WORKSPACE}/go"
    env.GOPATH = GOPATH
    sh "mkdir -p ${GOPATH}/empty_to_overwrite"
    sh "rsync -a --delete ${GOPATH}{/empty_to_overwrite,}/"  // Remove any cruft
    echo "Initialized env.GOPATH: ${env.GOPATH}"
}

def proxy_setup() {
    // Take load balancer from https://source.redhat.com/departments/it/digitalsolutionsdelivery/it-infrastructure/uis/uis_wiki/squid_proxy
    // proxy = "http://proxy.squi-001.prod.iad2.dc.redhat.com:3128"
    proxy = "http://proxy01.util.rdu2.redhat.com:3128"

    def no_proxy = [
        'localhost',
        '127.0.0.1',
        'openshiftapps.com',
        'engineering.redhat.com',
        'devel.redhat.com',
        'bos.redhat.com',
        'github.com',
        'registry.redhat.io',
        'api.openshift.com',
        'quay.io',
        'cdn.quay.io',
        'cdn01.quay.io',
        'cdn02.quay.io',
        'cdn03.quay.io'
    ]

    env.https_proxy = proxy
    env.http_proxy = proxy
    env.no_proxy = no_proxy.join(',')
}

def kinit() {
    echo "Initializing ocp-build kerberos credentials"
    // The '-f' ensures that the ticket is forwarded to remote hosts when ssh'ing.
    withCredentials([file(credentialsId: 'exd-ocp-buildvm-bot-prod.keytab', variable: 'DISTGIT_KEYTAB_FILE'), string(credentialsId: 'exd-ocp-buildvm-bot-prod.user', variable: 'DISTGIT_KEYTAB_USER')]) {
        try {
            retry(3) {
                sh 'if ! kinit -f -k -t $DISTGIT_KEYTAB_FILE $DISTGIT_KEYTAB_USER; then sleep 3; false; fi'
            }
        } catch (e) {
            echo "Failed to renew kerberos ticket. Assuming the ticket has been renewed recently enough"
            echo "${e}"
        }
    }
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
}

def registry_quay_dev_login() {
    // Login to the openshift-release-dev/ocp-v4.0-art-dev registry
    // Despite the name, this is the location for both dev and production images.

    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_dev_registry.quay.io',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'docker login -u openshift-release-dev+art_quay_dev -p "$PASSWORD" quay.io'
    }
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

def setup_venv(use_python38=false) {
    // Preparing venv for ART tools (doozer and elliott)
    // The following commands will run automatically every time one of our jobs
    // loads buildlib (ideally, once per pipeline)
    VIRTUAL_ENV = "${env.WORKSPACE}/art-venv"
    commonlib.shell(script: "rm -rf ${VIRTUAL_ENV}")

    // Used by tools that don't use buildlib.doozer() / .elliott()
    DOOZER_BIN = "${VIRTUAL_ENV}/bin/python3 art-tools/doozer/doozer"
    ELLIOTT_BIN = "${VIRTUAL_ENV}/bin/python3 art-tools/elliott/elliott"

    if (use_python38) {
        commonlib.shell(script: """
        if [[ -f /bin/scl ]]; then
            scl enable rh-python38 -- python3 -m venv --system-site-packages --symlinks ${VIRTUAL_ENV}
        else
            python3.8 -m venv --system-site-packages --symlinks ${VIRTUAL_ENV}
        fi
        """)
    } else {
        commonlib.shell(script: "python3 -m venv --system-site-packages --symlinks ${VIRTUAL_ENV}")
    }

    env.VIRTUAL_ENV = "${VIRTUAL_ENV}"
    env.PATH = "${VIRTUAL_ENV}/bin:${env.WORKSPACE}/art-tools/elliott:${env.WORKSPACE}/art-tools/doozer:${env.PATH}"

    commonlib.shell(script: "pip install --upgrade pip")
    if (params.DOOZER_COMMIT) {
        where = DOOZER_COMMIT.split('@')
        commonlib.shell(script: "rm -rf art-tools/doozer ; cd art-tools; git clone https://github.com/${where[0]}/doozer.git; cd doozer; git checkout ${where[1]}")
    }
    commonlib.shell(script: "pip install -e art-tools/elliott/ -e art-tools/doozer/ -e pyartcd/")
    out = sh(
        script: 'pip list | grep "doozer\\|elliott"',
        returnStdout: true
    )
    echo "Installed pyartcd:"
    echo "${out}"
}

def doozer(cmd, opts=[:]){
    withCredentials([
        usernamePassword(
            credentialsId: 'art-dash-db-login',
            passwordVariable: 'DOOZER_DB_PASSWORD', usernameVariable: 'DOOZER_DB_USER'),
        file(
            credentialsId: 'art-jenkins-ldap-serviceaccount-private-key',
            variable: 'RHSM_PULP_KEY'),
        file(
            credentialsId: 'art-jenkins-ldap-serviceaccount-client-cert',
            variable: 'RHSM_PULP_CERT'),
    ]) {
        withEnv(['DOOZER_DB_NAME=art_dash']) {
            return commonlib.shell(
                returnStdout: opts.capture ?: false,
                alwaysArchive: opts.capture ?: false,
                script: "doozer --assembly=${params.ASSEMBLY ?: 'stream'} ${cleanWhitespace(cmd)}")
        }
    }
}

def elliott(cmd, opts=[:]){
    return commonlib.shell(
        returnStdout: opts.capture ?: false,
        alwaysArchive: opts.capture ?: false,
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

def param(type, name, value) {
    return [$class: type + 'ParameterValue', name: name, value: value]
}

def sync_images(major, minor, mail_list, assembly, operator_nvrs = null, doozer_data_path, doozer_data_gitref = "") {
    // Run an image sync after a build. This will mirror content from
    // internal registries to quay. After a successful sync an image
    // stream is updated with the new tags and pullspecs.
    // Also update the app registry with operator manifests.
    // If operator_nvrs is given, will only build manifests for specified operator NVRs.
    // If builds don't succeed, email and set result to UNSTABLE.
    if(major < 4) {
        currentBuild.description = "Invalid sync request: Sync images only applies to 4.x+ builds"
        error(currentBuild.description)
    }
    def fullVersion = "${major}.${minor}"
    def results = []

    parallel "build-sync": {
        if (assembly == "test") {
            echo "Skipping build-sync job for test assembly"
        } else {
            results.add build(job: 'build%2Fbuild-sync', propagate: false, parameters: [
                param('String', 'BUILD_VERSION', fullVersion),  // https://stackoverflow.com/a/53735041
                param('String', 'ASSEMBLY', assembly),
                param('String', 'DOOZER_DATA_PATH', doozer_data_path),
                param('Boolean', 'DRY_RUN', params.DRY_RUN),
            ])
        }
    }, "olm-bundle": {
        if (operator_nvrs != []) {  // If operator_nvrs is given but empty, we will not build bundles.
            results.add build(job: 'build%2Folm_bundle', propagate: false, parameters: [
                param('String', 'BUILD_VERSION', fullVersion),  // https://stackoverflow.com/a/53735041
                param('String', 'ASSEMBLY', assembly),
                param('String', 'DOOZER_DATA_PATH', doozer_data_path),
                param('String', 'DOOZER_DATA_GITREF', doozer_data_gitref),
                param('String', 'OPERATOR_NVRS', operator_nvrs != null ? operator_nvrs.join(",") : ""),
                param('Boolean', 'DRY_RUN', params.DRY_RUN),
            ])
        } else {
            echo "No operators nvrs, will not build bundles"
        }
    }
    if ( results.any { it.result != 'SUCCESS' } ) {
        if (!params.DRY_RUN) {
            commonlib.email(
                replyTo: mail_list,
                to: "aos-art-automation+failed-image-sync@redhat.com",
                from: "aos-art-automation@redhat.com",
                subject: "Problem syncing images after ${currentBuild.displayName}",
                body: "Jenkins console: ${commonlib.buildURL('console')}",
            )
        }
    }
}

/**
 * Parse record.log from Doozer into a map. The map will be keyed by the type
 * of operation performed. The values will be a list of maps. Each of these
 * maps will contain the attributes for a single recorded operation of the top
 * level key's type. The
 * For example:
 * record_map['covscan'] = [
 *     [ 'distgit' : 'containers/ose-cli-artifacts',
 *       'owners'  : 'ccoleman@redhat.com,aos-master@redhat.com',
 *       ...
 *     ],
 *     [ 'distgit' : 'containers/openshift-enterprise-tests',
 *       'owners'  : 'aos-master@redhat.com',
 *       ...
 *     ],
 *     ...
 * ]
 */
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
// @param gaOnly <boolean>: If you only want group arches and do not care about arches_override.
//
// @return arches <List>: A list of the arches built for this branch
def branch_arches(String branch, boolean gaOnly=false) {
    echo("Fetching group config for '${branch}'")

    // Check if arches_override has been specified. This is used in group.yaml
    // when we temporarily want to build for CPU architectures that are not yet GA.
    def arches_override = doozer("--group=${branch} config:read-group --yaml arches_override --default '[]'",
            [capture: true]).trim()
    def arches_override_list = readYaml(text: arches_override)
    if ( !gaOnly && arches_override_list ) {
        return arches_override_list
    }

    def arches = doozer("--group=${branch} config:read-group --yaml arches",
		   [capture: true]).trim()
    def arches_list = readYaml(text: arches)
    return arches_list
}

def get_failed_builds(Map record_log, Boolean fullRecord=false) {
    // Returns a map of distgit => task_url OR full record.log dict entry IFF the distgit's build failed
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

def get_successful_builds(Map record_log, Boolean fullRecord=false) {
    // Returns a map of distgit => task_url OR full record.log dict entry IFF the distgit's build succeeded
    builds = record_log.get('build', [])
    success_map = [:]
    for (i = 0; i < builds.size(); i++) {
        bld = builds[i]
        distgit = bld['distgit']
        if (bld['status'] == '0') {
            success_map[distgit] = fullRecord ? bld : bld['task_url']
        }
    }

    return success_map
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

def notify_bz_info_missing(doozerWorking, buildVersion) {
    record_log = parse_record_log(doozerWorking)
    bz_notify_entries = record_log.get('bz_maintainer_notify', [])
    for (bz_notify in bz_notify_entries) {
        public_upstream_url = bz_notify['public_upstream_url']
        distgit = bz_notify['distgit']

        owners = bz_notify.get('owners', null)

        email_subject = "[ACTION REQUIRED] Bugzilla component information missing for image ${distgit} in OCP v${buildVersion}"

        explanation_body = """
Why am I receiving this?
------------------------
You are receiving this message because you are listed as an owner for an
OpenShift related image - or you recently made a modification to the definition
of such an image in github.

To comply with prodsec requirements, all images in the OpenShift product
should identify their Bugzilla component. To accomplish this, ART
expects to find Bugzilla component information in the default branch of
the image's upstream repository or requires it in ART image metadata.

What should I do?
------------------------
There are two options to supply Bugzilla component information.
1) The OWNERS file in the default branch (e.g. main / master) of ${public_upstream_url}
   can be updated to include the bugzilla component information.

2) The component information can be specified directly in the
   ART metadata for the image ${distgit}.

Details for either approach can be found here:
https://docs.google.com/document/d/1V_DGuVqbo6CUro0RC86THQWZPrQMwvtDr0YQ0A75QbQ/edit?usp=sharing

Thanks for your help!
"""

        if (owners) {
            commonlib.email(
                    to: owners,
                    from: "aos-team-art@redhat.com",
                    subject: email_subject,
                    body: explanation_body)
        }
    }

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
            body: explanation_body)
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
                container_log = "Unfortunately there were no container build logs; something else about the build failed."
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

def cleanWorkspace() {
    cleanWs(cleanWhenFailure: false, notFailBuild: true)
    dir("${workspace}@tmp") {
        deleteDir()
    }
    dir("${workspace}@script") {
        deleteDir()
    }
    dir("${workspace}@libs") {
        deleteDir()
    }
}

WORKDIR_COUNTER=0 // ensure workdir cleanup can be invoked multiple times per job
def cleanWorkdir(workdir, synchronous=false) {
    // get a fresh workdir; removing the old one can be synchronous or background.

    // **WARNING** workdir should generally NOT be env.WORKSPACE; this is where the job code is checked out,
    // including supporting scripts and such. Usually you don't want to wipe that out, so use a subdirectory.

    // NOTE: if wrapped in commonlib.shell, this would wait for the background process;
    // this is designed to run instantly and never fail, so just run it in a normal shell.
    to_remove = "${workdir}.rm.${currentBuild.number}.${WORKDIR_COUNTER}"
    empty = "empty.${currentBuild.number}.${WORKDIR_COUNTER}"
    sh """
        mkdir -p ${workdir}/${empty}   # create empty subdir to use as template to overwrite quickly
        mv ${workdir} ${to_remove}     # move workdir aside to remove at leisure
        mkdir -p ${workdir}            # create another to use immediately
    """

    // use rsync --delete instead of rm -rf for improved speed:
    // https://unix.stackexchange.com/questions/37329/efficiently-delete-large-directory-containing-thousands-of-files
    // also, it rewrites directory permissions instead of just accepting them like rm -rf does

    if (synchronous) {
        // Some jobs can make large doozer_workings faster than we can remove them.
        // Those jobs should call with synchronous.
        sh """
            sudo rsync -a --delete ${to_remove}{/${empty},}/
            rmdir ${to_remove}
        """
    } else {
        sh """
            # see discussion at https://stackoverflow.com/a/37161006 re:
            JENKINS_NODE_COOKIE=dontKill BUILD_ID=dontKill nohup bash -c 'sudo rsync -a --delete ${to_remove}{/${empty},}/ && rmdir ${to_remove}' &
        """
    }

    WORKDIR_COUNTER++
}

def defaultReleaseFor(stream) {
    return stream.startsWith("3") ? "1" : (new Date().format("yyyyMMddHHmm") + ".p?")
}

@NonCPS
String extractAdvisoryId(String elliottOut) {
    def matches = (elliottOut =~ /https:\/\/errata\.devel\.redhat\.com\/advisory\/([0-9]+)/)
    matches[0][1]
}

/**
 * Returns the status of freeze_automation in the group.yml
 */
def getAutomationState(doozerOpts){
    String freeze_automation = doozer("${doozerOpts} config:read-group --default 'no' freeze_automation",
            [capture: true]).trim()
    return freeze_automation
}

/**
 * Checks the status of the freeze_automation key in the group.yml and
 * returns whether the current run is permitted accordingly.
 * @param doozerOpts A string containing, at least, a `--group` parameter.
 */
def isBuildPermitted(doozerOpts) {
    // check whether the group should be built right now
    def freeze_automation = getAutomationState(doozerOpts)

    def builderEmail
    wrap([$class: 'BuildUser']) {
        builderEmail = env.BUILD_USER_EMAIL
    }

    echo "Group's freeze_automation flag: ${freeze_automation}"
    echo "Builder email: ${builderEmail}"

    if (freeze_automation in ["yes", "True"]) {  // yaml parses unquoted "yes" as a boolean... accept either
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

def get_releases_config(String group) {
    // FIXME: This method doesn't handle assembly inheritance.
    def r = httpRequest(
        url: "https://raw.githubusercontent.com/openshift-eng/ocp-build-data/${URLEncoder.encode(group, 'utf-8')}/releases.yml",
        httpMode: 'GET',
        timeout: 30,
        validResponseCodes: '200:404',
    )
    if (r.status == 200)
        return readYaml(text: r.content)
    if (r.status == 404)
        return null
    error("Unable to get releases config: HTTP Error ${r.status}")
}

this.initialize()

return this
