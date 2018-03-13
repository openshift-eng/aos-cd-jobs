#!/usr/bin/env groovy

properties(
    [
        [ $class : 'ParametersDefinitionProperty', parameterDefinitions: [
                [
                    name: 'JENKINS_VERSION',
                    description: 'Jenkins version to update to. Example: 2.89.2',
                    $class: 'hudson.model.StringParameterDefinition',
                ],
                [
                    name: 'OCP_RELEASE',
                    description: 'OCP target release',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: ['3.15', '3.14', '3.13', '3.12', '3.11', '3.10', '3.9', '3.8', '3.7', '3.6'].join('\n'),
                    defaultValue: '3.10'
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    description: 'Success Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com,gmontero@redhat.com,bparees@redhat.com'
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com,gmontero@redhat.com,bparees@redhat.com'
                ],
                [
                    name: 'TARGET_NODE',
                    description: 'Jenkins agent node',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'openshift-build-1'
                ],
                [
                    $class: 'hudson.model.BooleanParameterDefinition', 
                    defaultValue: false,
                    description: 'Mock run to pickup new Jenkins parameters?', 
                    name: 'MOCK'
                ],            
            ]
        ],
        disableConcurrentBuilds()
    ]
)

OCP_BRANCH="rhaos-${OCP_RELEASE}-rhel-7"

def mail_success() {
    distgit_link = "http://pkgs.devel.redhat.com/cgit/rpms/jenkins/?h=${OCP_BRANCH}"

    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "jenkins RPM for OCP v${OCP_RELEASE} updated in dist-git",
        body: """The Jenkins RPM for ${OCP_RELEASE} has been updated in dist-git:
${distgit_link}

Jenkins version: ${JENKINS_VERSION}

RPM update job: ${env.BUILD_URL}
""");
}

def mail_failure(err) {

    mail(
        to: "${MAIL_LIST_FAILURE}",
        from: "aos-cd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "Error during jenkins OCP v${OCP_RELEASE} RPM update on dist-git",
        body: """The job to update the jenkins RPM in dist-git encountered an error:
${err}

Jenkins job: ${env.BUILD_URL}
""");
}

node(TARGET_NODE) {

    checkout scm

    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    buildlib.kinit()       // Sets up credentials for dist-git access

    try {

        stage ("bump jenkins version") {
            sh "./bump-jenkins.sh ${JENKINS_VERSION} ${OCP_RELEASE}"
        }

        mail_success()

    } catch (err) {

        mail_failure(err)

        // Re-throw the error in order to fail the job
        throw err
    }
}
