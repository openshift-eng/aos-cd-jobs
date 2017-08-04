
def commonlib = load("pipeline-scripts/common.groovy")

commonlib.initialize()

def initialize() {
    // Login to legacy registry.ops to enable pushes
    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'registry-push.ops.openshift.com',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'sudo docker login -u $USERNAME -p "$PASSWORD" registry-push.ops.openshift.com'
    }

    // Login to new registry.ops to enable pushes
    withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_registry.reg-aws',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'oc login -u $USERNAME -p $PASSWORD https://api.reg-aws.openshift.com'

        // Writing the file out is all to avoid displaying the token in the Jenkins console
        writeFile file:"docker_login.sh", text:'''#!/bin/bash
        sudo docker login -u $USERNAME -p $(oc whoami -t) registry.reg-aws.openshift.com:443
        '''
        sh 'chmod +x docker_login.sh'
        sh './docker_login.sh'
    }

    echo "Adding git managed ose_images.sh directory to PATH"
    env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"
}

def initialize_go_dir() {
    env.GOPATH = "${env.WORKSPACE}/go"
    sh "rm -rf ${env.GOPATH}"  // Remove any cruft
    sh "mkdir -p ${env.GOPATH}"
    echo "Initialized env.GOPATH: ${env.GOPATH}"
}

def initialize_openshift_dir() {
    this.initialize_go_dir()
    env.OPENSHIFT_DIR = "${env.GOPATH}/src/github.com/openshift/"
    sh "mkdir -p ${env.OPENSHIFT_DIR}"
    echo "Initialized env.GOPATH: ${env.OPENSHIFT_DIR}"
}

def initialize_ose_dir() {
    initialize_go_dir()
    dir( env.OPENSHIFT_DIR ) {
        sh 'git clone git@github.com:openshift/ose.git'
    }
    env.OSE_DIR = "${env.OPENSHIFT_DIR}/ose"
    echo "Initialized env.OSE_DIR: ${env.OSE_DIR}"
}

// Matcher is not serializable; use NonCPS
@NonCPS
def extract_rpm_version( spec_content ) {
    def ver_matcher = spec_content =~ /^\s*Version:\s*([.0-9]+)/
    if ( ! ver_matcher ) { // Groovy treats matcher as boolean in this context
        error( "Unable to extract Version field from RPM spec" )
    }
    return ver_matcher[0][1]
}

// Matcher is not serializable; use NonCPS
@NonCPS
def extract_rpm_release_prefix(spec_content ) {
    def rel_matcher = spec_content =~ /^\s*Release:\s*([.a-zA-Z0-9+-]+)/  // Do not match vars like %{?dist}
    if ( ! rel_matcher ) { // Groovy treats matcher as boolean in this context
        error( "Unable to extract Release field from RPM spec" )
    }
    return rel_matcher[0][1]
}

def get_ose_master_version() {
    this.initialize_ose_dir()
    dir( env.OSE_DIR ) {
        def spec_content = readFile( "origin.spec" )
        version = extract_rpm_version( spec_content )
        fields = version.tokenize('.')
        def major_minor = fields[0] + "." + fields[1]   // Turn "3.6.5" into "3.6"

        // Perform some sanity checks

        if ( sh( returnStdout: true, script: 'git ls-remote --heads git@github.com:openshift/origin.git release-${major_minor}' ).trim() != "" ) {
            error( "origin has a release branch for ${major_minor}; ose should have a similar enterprise branch and ose#master's spec Version minor should be bumped" )
        }

        if ( sh( returnStdout: true, script: 'git ls-remote --heads git@github.com:openshift/openshift-ansible.git release-${major_minor}' ).trim() != "" ) {
            error( "openshift-ansible has a release branch for ${major_minor}; ose should have a similar enterprise branch and ose#master's spec Version minor should be bumped" )
        }

        // origin-web-console does not work like the other repos. It always has a enterprise branch for any release in origin#master.
        // origin-web-console#master contains changes for the latest origin-web-console#enterprise-X.Y which need to be be merged into
        // it when building X.Y.
        if ( sh( returnStdout: true, script: 'git ls-remote --heads git@github.com:openshift/origin-web-console.git enterprise-${major_minor}' ).trim() == "" ) {
            error( "origin-web-console does not yet have an enterprise branch for ${major_minor}; one should be created" )
        }

        return version
    }
}

def get_ose_master_release_prefix() {
    this.initialize_ose_dir()
    dir( env.OSE_DIR ) {
        def spec_content = readFile( "origin.spec" )
        return extract_rpm_release_prefix( spec_content )
    }
}

return this