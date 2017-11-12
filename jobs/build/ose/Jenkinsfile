#!/usr/bin/env groovy

// Update OSE_MASTER when the version in ose/master changes
def OSE_MASTER = "3.8"

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

// Matchers are not serializable, so use @NonCPS
@NonCPS
def version_parse(spec_content) {
    def matcher = spec_content =~ /Version:\s*([.0-9]+)/
    if ( ! matcher ) {
        error( "Unable to extract RPM spec Version" )
    }
    def ver = matcher[0][1]
    // Extract "Release" field as well, but do not include %{?dist} type variables
    matcher = spec_content =~ /Release:\s*([.a-zA-Z0-9+-]+)/
    if ( ! matcher ) {
        error( "Unable to extract RPM spec Release" )
    }
    def rel = matcher[0][1]
    return ver + "-" + rel
}

def version(spec_file) {
    return version_parse(readFile(spec_file))
}

def mail_success(version) {

    def target = "(Release Candidate)"
    def mirrorURL = "https://mirror.openshift.com/enterprise/enterprise-${version.substring(0,3)}"

    if ( BUILD_MODE == "online:int" ) {
        target = "(Integration Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-int"
    }

    if ( BUILD_MODE == "online:stg" ) {
        target = "(Stage Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-stg"
    }

    def oaBrewURL = readFile("results/openshift-ansible-brew.url")
    def oseBrewURL = readFile("results/ose-brew.url")
    def puddleName = readFile("results/ose-puddle.name")
    def changelogs = readFile("results/changelogs.txt")

    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cd@redhat.com",
        replyTo: 'smunilla@redhat.com',
        subject: "[aos-cicd] New build for OpenShift ${target}: ${version}",
        body: """\
OpenShift Version: v${version}

Puddle: http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${version.substring(0,3)}/${puddleName}
  - Mirror: ${mirrorURL}/${puddleName}
  - Images have been built for this puddle
  - Images have been pushed to registry.reg-aws.openshift.com:443         (Get pull acceess [1])
  [1] https://github.com/openshift/ops-sop/blob/master/services/opsregistry.asciidoc#using-the-registry-manually-using-rh-sso-user

Brew:
  - Openshift: ${oseBrewURL}
  - OpenShift Ansible: ${oaBrewURL}

Jenkins job: ${env.BUILD_URL}

${changelogs}
""");
}

// Expose properties for a parameterized build
properties(
        [
            buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '720')),
            [$class : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'openshift-build-1', description: 'Jenkins agent node', name: 'TARGET_NODE'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-cicd@redhat.com, aos-qe@redhat.com,jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Enable intra-day build hack for CL team CI?', name: 'EARLY_LATEST_HACK'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "enterprise\nenterprise:pre-release\nonline:int\nonline:stg", description:
'''
enterprise                {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
enterprise:pre-release    {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
online:stg                {origin,origin-web-console,openshift-ansible}/stage -> online-stg yum repo<br>
''', name: 'BUILD_MODE'],
                          [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?.', name: 'MOCK'],
                  ]
            ],
            disableConcurrentBuilds()
        ]
)

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

prev_build = "not defined yet"

// Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
echo "${TARGET_NODE}, ${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], BUILD_MODE:${BUILD_MODE}, EARLY_LATEST_HACK:${EARLY_LATEST_HACK}"

node(TARGET_NODE) {
    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}.?? (${BUILD_MODE})"

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


    if ( OSE_MINOR.toInteger() > 6 ) {
        error( "This pipeline is only designed for versions <= 3.6" )
    }

    set_workspace()

    // oit_working must be in WORKSPACE in order to have artifacts archived
    OIT_WORKING = "${WORKSPACE}/oit_working"
    env.OIT_WORKING = OIT_WORKING
    //Clear out previous work
    sh "rm -rf ${OIT_WORKING}"
    sh "mkdir -p ${OIT_WORKING}"

    stage('Merge and build') {
        try {

            checkout scm

            env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"

            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                env.OSE_MASTER = "${OSE_MASTER}"
                env.BUILD_MODE = "${BUILD_MODE}"
                env.EARLY_LATEST_HACK = "${EARLY_LATEST_HACK}"

                prev_build = sh(returnStdout: true, script: "brew latest-build --quiet rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()

                sh "./scripts/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"
            }

            thisBuildVersion = version("${env.WORKSPACE}/src/github.com/openshift/ose/origin.spec")

            currentBuild.displayName = "#${currentBuild.number} - ${thisBuildVersion} (${BUILD_MODE})"

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(thisBuildVersion)

        } catch ( err ) {

            ATTN=""
            try {
                new_build = sh(returnStdout: true, script: "brew latest-build --quiet rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()
                echo "Comparing new_build (" + new_build + ") and prev_build (" + prev_build + ")"
                if ( new_build != prev_build ) {
                    // Untag anything tagged by this build if an error occured at any point
                    sh "brew --user=ocp-build untag-build rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate ${new_build}"
                }
            } catch ( err2 ) {
                ATTN=" - UNABLE TO UNTAG!"
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}${ATTN}",
                    body: """Encoutered an error while running merge-and-build.sh: ${err}

Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            try {
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/*.log"
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/brew-logs/**"
            } catch( aae ) {}
        }

    }
}
