#!/usr/bin/env groovy

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
    def mirrorURL = "https://mirror.openshift.com/enterprise/enterprise-${version.substring(0,3)}/"

    if ( BUILD_MODE == "online/master" ) {
        target = "Online-int"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-int/"
    }
    if ( BUILD_MODE == "online/stg" ) {
        target = "Online-stg"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-stg/"
    }

    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cd@redhat.com",
        replyTo: 'tdawson@redhat.com',
        subject: "[aos-devel] New Puddle for OpenShift ${target}: ${version}",
        body: """\
v${version}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synced to mirrors : ${mirrorURL}

Jenkins job: ${env.BUILD_URL}
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
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-devel@redhat.com, aos-qe@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,tdawson@redhat.com,smunilla@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "online/master\nonline/stg\nenterprise/master\nenterprise/release", description: '''online/master openshift/origin/master -> online-int yum repo<br>
online/stg openshift/origin/stg -> online-stg yum repo<br>
enterprise/master  openshift/origin/master ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
enterprise/release  openshift/origin/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>''', name: 'BUILD_MODE'],
                              [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Force openshift-ansible build?', name: 'FORCE_OPENSHIFT_ANSIBLE_BUILD'],
                              [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'OSE master updated after a conflict', name: 'IGNORE_OSE_REBASE'],
                      ]
             ]]
    )
    
    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], FORCE_OPENSHIFT_ANSIBLE_BUILD:${FORCE_OPENSHIFT_ANSIBLE_BUILD}, BUILD_MODE:${BUILD_MODE}"

    set_workspace()
    stage('Merge and build') {
        try {
            checkout scm

            checkout changelog: false, poll: false,
                       scm: [$class: 'GitSCM', branches: [[name: 'build-scripts']],
                                doGenerateSubmoduleConfigurations: false,
                                extensions: [   [$class: 'RelativeTargetDirectory', relativeTargetDir: 'build-scripts'],
                                                [$class: 'WipeWorkspace']], submoduleCfg: [],
                                                userRemoteConfigs: [[url: 'https://github.com/openshift/aos-cd-jobs.git']]]

            env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"

            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                env.BUILD_MODE = "${BUILD_MODE}"
                env.FORCE_OPENSHIFT_ANSIBLE_BUILD = "${FORCE_OPENSHIFT_ANSIBLE_BUILD}"
                sh "./scripts/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(version("${env.WORKSPACE}/src/github.com/openshift/ose/origin.spec"))


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
