#!/usr/bin/env groovy

properties(
    [
        [ $class : 'ParametersDefinitionProperty', parameterDefinitions: [
                [
                    name: 'JENKINS_VERSION',
                    description: 'Minimum required Jenkins version',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: '2.42'
                ],
                [
                    name: 'OCP_RELEASE',
                    description: 'OCP target release',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: ['3.15', '3.14', '3.13', '3.12', '3.11', '3.10', '3.9','3.8','3.7', '3.6', '3.5', '3.4', '3.3'].join('\n'),
                    defaultValue: '3.10'
                ],
                [
                    name: 'PLUGIN_LIST',
                    description: 'List of plugin:version to include, one per line',
                    $class: 'hudson.model.TextParameterDefinition'
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

def mail_success() {

    jenkins_major = JENKINS_VERSION.tokenize('.')[0].toString()

    distgit_link = "http://pkgs.devel.redhat.com/cgit/rpms/jenkins-${jenkins_major}-plugins/?h=rhaos-${OCP_RELEASE}-rhel-7"

    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cicd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "jenkins plugins RPM for OCP ${OCP_RELEASE} updated in dist-git",
        body: """The Jenkins plugins RPM for OCP ${OCP_RELEASE} has been updated in dist-git:
${distgit_link}

Minimum Jenkins version: ${JENKINS_VERSION}

Plugin list:
${PLUGIN_LIST}

Plugin RPM update job: ${env.BUILD_URL}
""");
}

def mail_failure(err) {

    mail(
        to: "${MAIL_LIST_FAILURE}",
        from: "aos-cicd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "Error during jenkins plugin RPM update on dist-git",
        body: """The job to update the jenkins plugins RPM in dist-git encountered an error:
${err}

Jenkins job: ${env.BUILD_URL}
""");
}

node(TARGET_NODE) {

    checkout scm

    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    buildlib.kinit()       // Sets up credentials for dist-git access

    try {
        stage ("prepare workspace") {

            // Temporary file to write the plugin list to
            tmpdir = pwd tmp:true
            plugin_file = "${tmpdir}/jenkins-plugins.txt"
            scripts_dir = "${env.WORKSPACE}/hacks/update-jenkins-plugins"
            // Note that collect-jenkins-plugins.sh has a hardcoded output dir:
            plugin_dir = "${scripts_dir}/working/hpis"

            writeFile file: plugin_file, text: PLUGIN_LIST
        }

        stage ("collect plugins") {
            withEnv(["PATH+SCRIPTS=${scripts_dir}"]) {
                sh "collect-jenkins-plugins.sh ${JENKINS_VERSION} ${plugin_file}"
            }
        }

        stage ("update dist-git") {
            withEnv(["PATH+SCRIPTS=${scripts_dir}"]) {
                sh "update-dist-git.sh ${JENKINS_VERSION} ${OCP_RELEASE} ${plugin_dir}"
            }
        }

        stage ("cleanup") {
            sh "rm -rf ${plugin_dir} ${plugin_file}"
        }

        mail_success()

    } catch (err) {

        mail_failure(err)

        // Re-throw the error in order to fail the job
        throw err
    }
}
