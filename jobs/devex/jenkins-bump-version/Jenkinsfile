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
                    name: 'OCP_BRANCH',
                    description: 'OCP target branch',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: ['rhaos-4.6-rhel-8', 'rhaos-4.6-rhel-7', 'rhaos-4.5-rhel-7', 'rhaos-4.4-rhel-7', 'rhaos-4.3-rhel-7', 'rhaos-4.2-rhel-7', 'rhaos-4.1-rhel-7', 'rhaos-4.0-rhel-7', 'rhaos-3.11-rhel-7', 'rhaos-3.10-rhel-7', 'rhaos-3.9-rhel-7','rhaos-3.8-rhel-7','rhaos-3.7-rhel-7', 'rhaos-3.6-rhel-7'].join('\n'),
                    defaultValue: 'rhaos-4.1-rhel-7'
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    description: 'Success Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'aos-art-automation+passed-jenkins-bump-version@redhat.com,openshift-dev-services+jenkins@redhat.com'
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'aos-art-automation+failed-jenkins-bump-version@redhat.com,openshift-dev-services+jenkins@redhat.com'
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
        disableResume(),
        disableConcurrentBuilds()
    ]
)

def mail_success() {
    distgit_link = "http://pkgs.devel.redhat.com/cgit/rpms/jenkins/?h=${OCP_BRANCH}"

    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-art-automation@redhat.com",
        replyTo: 'aos-team-art@redhat.com',
        subject: "jenkins RPM for ${OCP_BRANCH} updated in dist-git",
        body: """The Jenkins RPM for ${OCP_BRANCH} has been updated in dist-git:
${distgit_link}

Jenkins version: ${JENKINS_VERSION}

RPM update job: ${env.BUILD_URL}
""");
}

def mail_failure(err) {
    mail(
        to: "${MAIL_LIST_FAILURE}",
        from: "aos-art-automation@redhat.com",
        replyTo: 'aos-team-art@redhat.com',
        subject: "Error during jenkins ${OCP_BRANCH} RPM update on dist-git",
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
            sh "./bump-jenkins.sh ${JENKINS_VERSION} ${OCP_BRANCH}"
        }

        mail_success()

    } catch (err) {

        mail_failure(err)

        // Re-throw the error in order to fail the job
        throw err
    }
}
