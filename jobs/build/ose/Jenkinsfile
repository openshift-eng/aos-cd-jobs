#!/usr/bin/env groovy

// Update OSE_MASTER when the version in ose/master changes
def OSE_MASTER = "3.6"

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

def mail_success(version) {

    def target = "Enterprise"
    def mirrorURL = "https://mirror.openshift.com/enterprise/enterprise-${version.substring(0,3)}"

    if ( BUILD_MODE == "online:int" ) {
        target = "Online-int"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-int"
    }

    if ( BUILD_MODE == "online:stg" ) {
        target = "Online-stg"
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
        subject: "[aos-devel] New Puddle for OpenShift ${target}: ${version}",
        body: """\
OpenShift Version: v${version}

Puddle: ${mirrorURL}/${puddleName}
  - Images have been built for this puddle
  - Images have been pushed to registry.ops

Brew:
  - Openshift: ${oseBrewURL}
  - OpenShift Ansible: ${oaBrewURL}

Jenkins job: ${env.BUILD_URL}

${changelogs}
""");
}

node('buildvm-devops') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-devel@redhat.com, aos-qe@redhat.com,jupierce@redhat.com,smunilla@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "enterprise\nenterprise:pre-release\nonline:int\nonline:stg", description:
'''
enterprise                {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
enterprise:pre-release    {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
online:stg                {origin,origin-web-console,openshift-ansible}/stage -> online-stg yum repo<br>
''', name: 'BUILD_MODE'],
                      ]
             ]]
    )
    
    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], BUILD_MODE:${BUILD_MODE}"

    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}.?? (${BUILD_MODE})"
    
    set_workspace()
    stage('Merge and build') {
        try {

            if ( BUILD_MODE != "enterprise" && "${OSE_MAJOR}.${OSE_MINOR}" != OSE_MASTER ) {
                error("Unable to build older version ${OSE_MAJOR}.${OSE_MINOR} in online or pre-release mode: ${BUILD_MODE}. Only ${OSE_MASTER} can be built in this mode.")
            }

            checkout scm

            env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"

            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                env.OSE_MASTER = "${OSE_MASTER}"
                env.BUILD_MODE = "${BUILD_MODE}"
                sh "./scripts/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"
            }

            thisBuildVersion = version("${env.WORKSPACE}/src/github.com/openshift/ose/origin.spec")
            
            currentBuild.displayName = "#${currentBuild.number} - ${thisBuildVersion} (${BUILD_MODE})"
            
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(thisBuildVersion)

        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}",
                    body: """Encoutered an error while running merge-and-build.sh: ${err}

Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}
