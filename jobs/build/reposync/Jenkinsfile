node {
    checkout scm
    def commonlib = load("pipeline-scripts/commonlib.groovy")

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
                    commonlib.ocpVersionParam('SYNC_VERSION'),
                    [
                        name: 'REPO_TYPE',
                        description: 'Type of repos to sync',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: "unsigned\nsigned",
                        defaultValue: 'unsigned'
                    ],
                    commonlib.suppressEmailParam(),
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
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)

    currentBuild.displayName = "v${SYNC_VERSION} RepoSync"
    SYNC_DIR="/mnt/workspace/reposync"
    LOCAL_SYNC_DIR = "${SYNC_DIR}/${SYNC_VERSION}/"
    LOCAL_CACHE_DIR = "${SYNC_DIR}/cache/${SYNC_VERSION}/"

    MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
    MIRROR_PATH = "/srv/enterprise/reposync/${SYNC_VERSION}/"

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
                command += "beta:reposync --output ${LOCAL_SYNC_DIR} --cachedir ${LOCAL_CACHE_DIR} --repo-type ${REPO_TYPE} "
                buildlib.doozer command
            }

            stage("push to mirror") {
                sh "rsync -avzh --delete -e \"ssh -o StrictHostKeyChecking=no\" ${LOCAL_SYNC_DIR} ${MIRROR_TARGET}:${MIRROR_PATH} "
                buildlib.invoke_on_use_mirror("push.enterprise.sh")
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Error syncing v${SYNC_VERSION} repos",
            body: """Encountered an error while running OCP pipeline: ${err}

Jenkins job: ${env.BUILD_URL}
        """);

        currentBuild.result = "FAILURE"
        throw err
    } finally {
        commonlib.safeArchiveArtifacts(["doozer_working/*.log"])
    }
}
