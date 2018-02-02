#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
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

                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Specify only if the updater should run against a specific AMI without using tags to locate it.', name: 'SOURCE_AMI'],

                                 [$class: 'hudson.model.TextParameterDefinition', defaultValue: '', description: 'Line delimited tags (K=V) to use to find the AMI to update (the latest AMI with these tags will be located)', name: 'SOURCE_SEARCH_TAGS'],
                                 [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Select if search should find non-standard AMIs?.', name: 'SOURCE_NON_STANDARD'],

                                 [$class: 'hudson.model.TextParameterDefinition', defaultValue: '', description: 'Line delimited tags (K=V) to add to the resultant AMI (in addition to those from the source AMI)', name: 'DEST_ADD_TAGS'],
                                 [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Select if destination AMI be labeled non-standard', name: 'DEST_NON_STANDARD'],

                                 [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                         ]
                ],
        ]
)

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

node(TARGET_NODE) {
    /**
     *
     */
}
