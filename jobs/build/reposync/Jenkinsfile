
// Expose properties for a parameterized build
properties(
    [
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '',
                artifactNumToKeepStr: '',
                daysToKeepStr: '',
                numToKeepStr: '1000')),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'SYNC_VERSION',
                    description: 'OCP version of RPMs to sync',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "4.1\n4.0\n3.11\n3.10\n3.9\n3.8\n3.7\n3.6\n3.5\n3.4\n3.3",
                    defaultValue: '4.0'
                ],
                [
                    name: 'REPO_TYPE',
                    description: 'Type of repos to sync',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "unsigned\nsigned",
                    defaultValue: 'unsigned'
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
    ]
)

SYNC_DIR="/mnt/nfs/home/jenkins/reposync"
LOCAL_SYNC_DIR = "${SYNC_DIR}/${SYNC_VERSION}/"

MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
MIRROR_PATH = "/srv/enterprise/reposync/${SYNC_VERSION}/"


node("openshift-build-1") {
    checkout scm

    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }


    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
    }

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    //Clear out previous work
    sh "rm -rf ${DOOZER_WORKING}"
    sh "mkdir -p ${DOOZER_WORKING}"

    try {
        sshagent(['openshift-bot']) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot

            stage("sync repos to local") {
                command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${SYNC_VERSION}' "
                command += "beta:reposync --output ${LOCAL_SYNC_DIR} --repo-type ${REPO_TYPE} "
                buildlib.doozer command
            }

            stage("push to mirror") {
                sh "rsync -avzh --delete -e \"ssh -o StrictHostKeyChecking=no\" ${LOCAL_SYNC_DIR} ${MIRROR_TARGET}:${MIRROR_PATH} "
                buildlib.invoke_on_use_mirror("push.enterprise.sh")
            }

            mail(to: "${MAIL_LIST_SUCCESS}",
                from: "aos-team-art@redhat.com",
                subject: "Successful reposync for v${SYNC_VERSION}",
                body: "Jenkins job: ${env.BUILD_URL}");
        }
    } catch (err) {
        mail(to: "${MAIL_LIST_FAILURE}",
             from: "aos-team-art@redhat.com",
             subject: "Error syncing v${SYNC_VERSION} repos",
             body: """Encountered an error while running OCP pipeline: ${err}

    Jenkins job: ${env.BUILD_URL}
    """);

        currentBuild.result = "FAILURE"
        throw err
    } finally {
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: "doozer_working/*.log"
        } catch (aae) {
        }
    }
}