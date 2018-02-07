#!/usr/bin/env groovy
import groovy.json.JsonOutput

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def convert_property_to_ansible_arg(ansible_arg, ansible_value) {
    def created_ansible_arg = ''
    if (!ansible_value.isEmpty()) {
        created_ansible_arg = " -e ${ansible_arg}=${ansible_value} "
    }

    return created_ansible_arg
}

def convert_boolean_property_to_ansible_arg(ansible_arg, ansible_value) {
    def created_ansible_arg = ''
    if (!ansible_value.toBoolean()) {
        created_ansible_arg = " -e ${ansible_arg}=${String.valueOf(ansible_value)} "
    }

    return created_ansible_arg
}

@NonCPS
def convert_string_to_json_ansible_arg(ansible_arg, key_value_pairs) {
    def created_ansible_arg = ""
    if (!ansible_value.isEmpty()) {
        split_lines = key_value_pairs.split('\n')
        def output_map = [:]
        for (String item : split_lines) {
            split_item = item.split('=')
            output_map[split_item[0]] = split_item[1]
        }

        created_ansible_arg = " -e ${ansible_arg}=${JsonOutput.toJson(output_map)} "
    }

    return created_ansible_arg
}

// Expose properties for a parameterized build
properties(
        [
                disableConcurrentBuilds(),
                [$class: 'ParametersDefinitionProperty',
                 parameterDefinitions:
                         [
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'openshift-build-1', description: 'Jenkins agent node', name: 'TARGET_NODE'],

                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-cicd@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],

                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Specify only if the updater should run against a specific AMI without using tags to locate it.', name: 'SOURCE_AMI_ID'],

                                 [$class: 'hudson.model.TextParameterDefinition', defaultValue: '', description: 'Line delimited tags (K=V) to use to find the AMI to update (the latest AMI with these tags will be located)', name: 'SOURCE_AMI_SEARCH_TAGS'],

                                 [$class: 'BooleanParameterDefinition', defaultValue: true, description: 'Select if search should find standard AMIs?.', name: 'SOURCE_AMI_STANDARD'],

                                 [$class: 'hudson.model.TextParameterDefinition', defaultValue: '', description: 'Line delimited tags (K=V) to add to the resultant AMI (in addition to those from the source AMI)', name: 'DEST_AMI_ADDITIONAL_TAGS'],

                                 [$class: 'BooleanParameterDefinition', defaultValue: true, description: 'Select if destination AMI to be labeled standard', name: 'DEST_AMI_STANDARD'],

                                 [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                         ]
                ],
        ]
)

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

node(TARGET_NODE) {
    try {
        checkout scm
        set_workspace()
        def buildlib = load('pipeline-scripts/buildlib.groovy')
        stage('venv') {
            sh '''
[ -e env/ ] || virtualenv env/
env/bin/pip install --upgrade pip
env/bin/pip install --upgrade ansible boto boto3
'''
        }
        stage('build') {
            withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'ami-build-creds']]) {
                withEnv(['ANSIBLE_HOST_KEY_CHECKING=False']) {
                    sshagent(['ami_builder_key']) {
                        buildlib.with_virtualenv('env') {
                            // we need to build the options to pass into the ansible script
                            def anible_arg_ami_id = convert_property_to_ansible_arg('cli_image_id', SOURCE_AMI_ID)
                            def anible_arg_ami_search_standard = convert_boolean_property_to_ansible_arg('g_play_ami_search_standard', SOURCE_AMI_STANDARD)
                            def anible_arg_ami_tag_standard = convert_boolean_property_to_ansible_arg('g_play_ami_tag_standard', DEST_AMI_STANDARD)
                            def ansible_arg_ami_search_tags = convert_string_to_json_ansible_arg('g_play_ami_search_tags', SOURCE_AMI_SEARCH_TAGS)
                            def ansible_arg_ami_dest_additional_tags = convert_string_to_json_ansible_arg('cli_ami_additional_tags', DEST_AMI_ADDITIONAL_TAGS)

                            def ansible_command = "ansible-playbook " + anible_arg_ami_id + anible_arg_ami_search_standard + anible_arg_ami_tag_standard + ansible_arg_ami_search_tags + ansible_arg_ami_dest_additional_tags + "update_base_ami.yml"
                            sh ansible_command
                        }
                    }
                }
            }
        }
    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "${MAIL_LIST_FAILURE}",
                from: 'aos-cd@redhat.com',
                subject: "Error building aws ami",
                body: """Encoutered an error while running build_ami.yml: ${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }
}
