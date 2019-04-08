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
                    name: 'MAIL_LIST_SUCCESS',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'aos-cicd@redhat.com',
                        'aos-qe@redhat.com'
                    ].join(','),
                    description: 'Success Mailing List'
               ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'tbielawa@redhat.com',
                        'jupierce@redhat.com',
                        'smunilla@redhat.com',
                        'sedgar@redhat.com',
                        'vdinh@redhat.com',
                        'ahaile@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'FORCE_REBUILD',
                    description: 'Force rebuild even if no changes are detected?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'BUILD_MODE',
                    description:
                        '''online:int      online/master -> https://mirror.openshift.com/enterprise/online-openshift-scripts-int/ <br>
online:stg      online/stage -> https://mirror.openshift.com/enterprise/online-openshift-scripts-stg/ <br>
pre-release     online/master -> https://mirror.openshift.com/enterprise/online-openshift-scripts/X.Y <br>
release         online/online-X.Y.Z -> https://mirror.openshift.com/enterprise/online-openshift-scripts/X.Y <br>''',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "online:int",
                        "online:stg",
                        "pre-release",
                        "release"
                    ].join("\n")
                ],
                [
                    name: 'RELEASE_VERSION',
                    description: 'Release version (matches version in branch name for release builds)',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: [
                        "3.6.0",
                        "3.7.0"
                    ].join("\n"),
                    defaultValue: '3.6.0'
                ],
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?.',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
            ]
        ],
    ]
)

// Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
echo "${TARGET_NODE}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], FORCE_REBUILD:${FORCE_REBUILD}, BUILD_MODE:${BUILD_MODE}"

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

node(TARGET_NODE) {

    set_workspace()

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    env.DOOZER_WORKING = DOOZER_WORKING
    buildlib.cleanWorkdir(DOOZER_WORKING)

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

    stage('Merge and build') {
        try {
            checkout scm
            env.BUILD_MODE = "${BUILD_MODE}"
            env.RELEASE_VERSION = "${RELEASE_VERSION}"
            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                env.FORCE_REBUILD = "${FORCE_REBUILD}"
                sh "./scripts/merge-and-build-openshift-scripts.sh"
            }
        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cicd@redhat.com",
                    subject: "Error building openshift-online",
                    body: """Encoutered an error while running merge-and-build-openshift-scripts.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}
