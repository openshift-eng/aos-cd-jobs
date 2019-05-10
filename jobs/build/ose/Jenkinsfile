#!/usr/bin/env groovy

/**
 * The build/ose job can no longer be used to build ose/master. The support to do so
 * has been removed. It is only designed to build 3.3 through 3.6.
 */

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if (env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

// Matchers are not serializable, so use @NonCPS
@NonCPS
def version_parse(spec_content) {
    def matcher = spec_content =~ /Version:\s*([.0-9]+)/
    if (!matcher) {
        error("Unable to extract RPM spec Version")
    }
    def ver = matcher[0][1]
    // Extract "Release" field as well, but do not include %{?dist} type variables
    matcher = spec_content =~ /Release:\s*([.a-zA-Z0-9+-]+)/
    if (!matcher) {
        error("Unable to extract RPM spec Release")
    }
    def rel = matcher[0][1]
    return ver + "-" + rel
}

def version(spec_file) {
    return version_parse(readFile(spec_file))
}

def mail_success(version) {

    def target = "(Release Candidate)"
    def mirrorURL = "https://mirror.openshift.com/enterprise/enterprise-${version.substring(0, 3)}"

    if (BUILD_MODE == "online:int") {
        target = "(Integration Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-int"
    }

    if (BUILD_MODE == "online:stg") {
        target = "(Stage Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-stg"
    }

    def oaBrewURL = readFile("results/openshift-ansible-brew.url")
    def oseBrewURL = readFile("results/ose-brew.url")
    def puddleName = readFile("results/ose-puddle.name")
    def changelogs = readFile("results/changelogs.txt")

    PARTIAL = " "
    image_details = """
Images:
  - Images have been pushed to registry.reg-aws.openshift.com:443     (Get pull access [1])
    [1] https://github.com/openshift/ops-sop/blob/master/services/opsregistry.asciidoc#using-the-registry-manually-using-rh-sso-user"""

    mail_list = MAIL_LIST_SUCCESS
    if (!BUILD_CONTAINER_IMAGES) {
        PARTIAL = " RPM ONLY "
        image_details = ""
        // Just inform key folks about RPM only build; this is just prepping for an advisory.
        mail_list = MAIL_LIST_FAILURE
    }

    mail(
            to: "${mail_list}",
            from: "aos-cicd@redhat.com",
            subject: "[aos-cicd] New${PARTIAL}build for OpenShift ${target}: ${version}",
            body: """\
OpenShift Version: v${version}

RPMs:
    Puddle (internal): http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${version.substring(0, 3)}/${puddleName}
    External Mirror: ${mirrorURL}/${puddleName}
${image_details}

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
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '',
                artifactNumToKeepStr: '',
                daysToKeepStr: '',
                numToKeepStr: '720'
            )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'TARGET_NODE',
                    description: 'Jenkins agent node',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'openshift-build-1'
                ],
                [
                    name: 'OSE_MAJOR',
                    description: 'OSE Major Version',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ''
                ],
                [
                    name: 'OSE_MINOR',
                    description: 'OSE Minor Version',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ''
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    description: 'Success Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'aos-team-art@redhat.com',
                        'aos-cicd@redhat.com',
                        'aos-qe@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'aos-team-art@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'BUILD_MODE',
                    description: '''
enterprise                {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
enterprise:pre-release    {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/<br>
online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
online:stg                {origin,origin-web-console,openshift-ansible}/stage -> online-stg yum repo<br>
''',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "enterprise",
                        "enterprise:pre-release",
                        "online:int",
                        "online:stg"
                    ].join("\n")
                ],
                [
                    name: 'BUILD_CONTAINER_IMAGES',
                    description: 'Build container images?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: true
                ],
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?.',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
            ]
        ],
        disableConcurrentBuilds()
    ]
)

if (MOCK.toBoolean()) {
    error("Ran in mock mode to pick up any new parameters")
}

BUILD_CONTAINER_IMAGES = BUILD_CONTAINER_IMAGES.toBoolean()

prev_build = "not defined yet"

// Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
echo "${TARGET_NODE}, ${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], BUILD_MODE:${BUILD_MODE}"

node(TARGET_NODE) {
    rpmOnlyTag = ""
    if (!BUILD_CONTAINER_IMAGES) {
        rpmOnlyTag = " (RPM ONLY)"
    }
    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}.?? (${BUILD_MODE}${rpmOnlyTag})"

    // Login to new registry.ops to enable pushes
    withCredentials([[$class          : 'UsernamePasswordMultiBinding', credentialsId: 'creds_registry.reg-aws',
                      usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
        sh 'oc login -u $USERNAME -p $PASSWORD https://api.reg-aws.openshift.com'

        // Writing the file out is all to avoid displaying the token in the Jenkins console
        writeFile file: "docker_login.sh", text: '''#!/bin/bash
        sudo docker login -u $USERNAME -p $(oc whoami -t) registry.reg-aws.openshift.com:443
        '''
        sh 'chmod +x docker_login.sh'
        sh './docker_login.sh'
    }

    if (OSE_MINOR.toInteger() > 6) {
        error("This pipeline is only designed for versions <= 3.6")
    }

    try {
        // Clean up old images so that we don't run out of device mapper space
        sh "docker rmi --force \$(docker images  | grep v${OSE_MAJOR}.${OSE_MINOR} | awk '{print \$3}')"
    } catch (cce) {
        echo "Error cleaning up old images: ${cce}"
    }

    set_workspace()

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    env.DOOZER_WORKING = DOOZER_WORKING
    //Clear out previous work
    sh "rm -rf ${DOOZER_WORKING}"
    sh "mkdir -p ${DOOZER_WORKING}"

    stage('Merge and build') {
        try {

            checkout scm

            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                env.BUILD_MODE = "${BUILD_MODE}"
                env.BUILD_CONTAINER_IMAGES = "${BUILD_CONTAINER_IMAGES}"

                prev_build = sh(returnStdout: true, script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew latest-build --quiet rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()

                sh "./scripts/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"
            }

            thisBuildVersion = version("${env.WORKSPACE}/src/github.com/openshift/ose/origin.spec")

            currentBuild.displayName = "#${currentBuild.number} - ${thisBuildVersion} (${BUILD_MODE})"

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(thisBuildVersion)

        } catch (err) {

            ATTN = ""
            try {
                new_build = sh(returnStdout: true, script: "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew latest-build --quiet rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()
                echo "Comparing new_build (" + new_build + ") and prev_build (" + prev_build + ")"
                if (new_build != prev_build) {
                    // Untag anything tagged by this build if an error occured at any point
                    sh "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew --user=ocp-build untag-build rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7-candidate ${new_build}"
                }
            } catch (err2) {
                ATTN = " - UNABLE TO UNTAG!"
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cicd@redhat.com",
                    subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}${ATTN}",
                    body: """Encoutered an error while running merge-and-build.sh: ${err}

Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            try {
                archiveArtifacts allowEmptyArchive: true, artifacts: "doozer_working/*.log"
                archiveArtifacts allowEmptyArchive: true, artifacts: "doozer_working/brew-logs/**"
            } catch (aae) {
            }
        }

    }
}
