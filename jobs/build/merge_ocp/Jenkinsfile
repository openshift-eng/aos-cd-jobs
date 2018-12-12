
// Expose properties for a parameterized build
properties(
    [
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '',
                artifactNumToKeepStr: '',
                daysToKeepStr: '',
                numToKeepStr: '1000')
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'VERSIONS',
                    description: 'CSV list of versions to run merge on.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: "3.9,3.10,3.11,4.0"
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    description: 'Success Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'aos-team-art@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'aos-team-art@redhat.com',
                        // 'aos-art-requests@redhat.com'
                    ].join(',')
                ],
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ]
            ]
        ],
        disableConcurrentBuilds()
    ]
)


TARGET_NODE = "openshift-build-1"
SSH_KEY_ID = "openshift-bot"

MERGE_VERSIONS = VERSIONS.split(',')
CURRENT_MASTER = "4.0"


node(TARGET_NODE) {
    checkout scm

    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }


    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
    }

    try {
        sshagent([SSH_KEY_ID]) {
            for(int i = 0; i < MERGE_VERSIONS.size(); ++i) {
                def VERSION = MERGE_VERSIONS[i]
                MERGE_WORKING = "${WORKSPACE}/${VERSION}"
                sh "rm -rf ${MERGE_WORKING}"
                sh "mkdir -p ${MERGE_WORKING}"

                if(VERSION == CURRENT_MASTER) {
                    UPSTREAM = "master"
                    DOWNSTREAM = "master"
                }
                else {
                    UPSTREAM = "release-${VERSION}"
                    DOWNSTREAM = "enterprise-${VERSION}"
                }

                stage("Merge ${VERSION}") {
                    try {
                        sh "./merge_ocp.sh ${MERGE_WORKING} ${DOWNSTREAM} ${UPSTREAM}"

                        echo "Success running ${VERSION} merge"

                        // AMH - No email for now. There would be WAY too may emails.
                        // mail(to: "${MAIL_LIST_SUCCESS}",
                        //     from: "aos-team-art@redhat.com",
                        //     subject: "Success merging OCP v${VERSION}",
                        //     body: "Success running OCP merge:\n${env.BUILD_URL}"
                        // );

                    } catch (err) {
                        currentBuild.result = "UNSTABLE"
                        echo "Error running ${VERSION} merge:\n${err}"
                        mail(to: "${MAIL_LIST_FAILURE}",
                            from: "aos-team-art@redhat.com",
                            subject: "Error merging OCP v${VERSION}",
                            body: "Encountered an error while running OCP merge:\n${env.BUILD_URL}\n\n${err}"
                        );
                    }
                }
            }
        }

        currentBuild.result = "SUCCESS"

        // AMH - No email for now. There would be WAY too may emails.
        // As this is supposed to run multiple times per day
        // mail(to: "${MAIL_LIST_SUCCESS}",
        //     from: "aos-team-art@redhat.com",
        //     subject: "Success merging OCP versions: ${VERSIONS}",
        //     body: "Success running OCP merges:\n${env.BUILD_URL}"
        // );

    } catch (err) {
        // This job is so simple that this should never really happen. But might as well have it.
        mail(to: "${MAIL_LIST_FAILURE}",
             from: "aos-team-art@redhat.com",
             subject: "Unexpected error during OCP Merge!",
             body: "Encountered an unexpected error while running OCP merge: ${err}"
        );

        currentBuild.result = "FAILURE"
        throw err
    }
}