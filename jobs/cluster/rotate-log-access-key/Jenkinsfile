#!/usr/bin/env groovy

node('buildvm-devops') {

    properties([
            [   $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'BASTION_HOST',
                        description: 'Bastion host\'s hostname',
                        defaultValue: 'use-tower2.ops.rhcloud.com'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'BASTION_USER',
                        description: 'Bastion host\'s username',
                        defaultValue: 'opsmedic'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'BASTION_CREDENTIALS',
                        description: 'Jenkins Credentials to ssh to bastion host for key gen',
                        defaultValue: 'rotate_logs_key'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'SECRETS_REPO',
                        description: 'Git repo for shared secrets',
                        defaultValue: 'git@github.com:openshift/shared-secrets.git'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'OSE_CREDENTIALS',
                        description: 'Credentials for the secrets repository',
                        defaultValue: 'openshift-bot'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        name: 'KEY_FILE',
                        description: 'Relative path to the key file inside the secrets repo',
                        defaultValue: 'online/logs_access_key'
                    ],
                    [
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'pep@redhat.com',
                        description: 'Failure Mailing List',
                        name: 'MAIL_LIST_FAILURE'
                    ],
                ]
            ],
            pipelineTriggers([[
                        $class: 'TimerTrigger',
                        spec: 'H 0 * * 1'  // every Monday around midnight
                    ]])
        ]
    )

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo """Parameters:
BASTION_HOST: ${BASTION_HOST}
BASTION_USER: ${BASTION_USER}
BASTION_CREDENTIALS: ${BASTION_CREDENTIALS}
SECRETS_REPO: ${SECRETS_REPO}
OSE_CREDENTIALS: ${OSE_CREDENTIALS}
KEY_FILE: ${KEY_FILE}
MAIL_LIST_FAILURE: ${MAIL_LIST_FAILURE}
"""

    try {

        stage('Checkout secrets repo') {
            checkout(
                $class: 'GitSCM',
                userRemoteConfigs: [
                    [
                        name: 'origin',
                        url: SECRETS_REPO,
                        credentialsId: OSE_CREDENTIALS
                    ]
                ],
                branches: [[ name: '*/master' ]]
            )
        }

        stage('Generate and install/rotate Key') {
            def new_key = null
            sshagent([BASTION_CREDENTIALS]) {
                echo "Generate new key and rotate authorized_keys"
                // This is performed by the command associated to this user/key, see
                // tower-scripts/bin/rotate-log-access-key.sh
                new_key = sh (
                    script: "ssh -o StrictHostKeyChecking=no ${BASTION_USER}@${BASTION_HOST}",
                    returnStdout: true
                )
            }
            writeFile file: KEY_FILE, text: new_key
        }

        stage('Push new key to shared secrets repo') {
            sshagent([OSE_CREDENTIALS]) {
                sh """
git add ${KEY_FILE}
git commit -m "New SSH key to gather cluster logs"
git push origin HEAD:master
"""
            }
        }

    } catch ( err ) {
        mail(to: "${MAIL_LIST_FAILURE}",
            from: "aos-cd@redhat.com",
            subject: "Error during SSH key rotation for cluster log collection",
            body: """Encoutered an error: ${err}

Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }
}

