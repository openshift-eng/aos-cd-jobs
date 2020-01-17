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
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('SYNC_VERSION'),
                    [
                        name: 'ARCH',
                        description: 'Architecture of repo to synchronize; must have full definition in group.yml for release',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [ 'x86_64', 'ppc64le', 's390x' ].join("\n"),
                        defaultValue: 'x86_64'
                    ],
                    [
                        name: 'REPO_TYPE',
                        description: 'Type of repos to sync',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: "unsigned\nsigned",
                        defaultValue: 'unsigned'
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-reposync@redhat.com',
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    buildlib.initialize(false)

    currentBuild.displayName = "v${SYNC_VERSION}_${ARCH}"
    REPOSYNC_BASE_DIR="/mnt/workspace/reposync"
    LOCAL_SYNC_DIR = "${REPOSYNC_BASE_DIR}/${SYNC_VERSION}"
    LOCAL_CACHE_DIR = "${REPOSYNC_BASE_DIR}_cache/${SYNC_VERSION}"

    MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
    MIRROR_REPOSYNC_BASE_DIR = "/srv/enterprise/reposync/"

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    DOOZER_WORKING = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(DOOZER_WORKING)

    try {
        lock('buildvm-yum') { // prevent simultaneous job runs from conflicting over yum lock
            sshagent(['openshift-bot']) {
                // To work on real repos, buildlib operations must run with the permissions of openshift-bot

                stage("sync repos to local") {
                    cacheDir = "${LOCAL_CACHE_DIR}_${ARCH}"

                    if ( ARCH == 'x86_64' ) {
                        // Match legacy location for x86_64
                        syncDir = "${LOCAL_SYNC_DIR}"
                    } else {
                        // Non x86_64 arch directories will have the arch as a suffix
                        syncDir = "${LOCAL_SYNC_DIR}_${ARCH}"
                    }

                    command = "--working-dir ${DOOZER_WORKING} --group 'openshift-${SYNC_VERSION}' "
                    command += "beta:reposync --output ${syncDir}/ --cachedir ${cacheDir}/ --repo-type ${REPO_TYPE} --arch ${ARCH}"
                    buildlib.doozer command

                    /**
                     * A bug in doozer once caused only noarch RPMs to be synced to the mirrors. Prevent this
                     * by making sure a minimum number of arch-specific RPMs actually exist locally before
                     * pushing the updated content to the mirrors.
                     */

                    sanityCheckRes = commonlib.shell(
                            returnAll: true,
                            script: "find ${syncDir} -name '*.${ARCH}.rpm' | wc -l"
                    )

                    if(sanityCheckRes.stdout.trim().toInteger() < 50){
                        error("Did not find a sufficient number of arch specific RPMs; human checks required!")
                    }

                }

                stage("push to mirror") {
                    sh "rsync -avzh --chmod=a+rwx,g-w,o-w --delete -e \"ssh -o StrictHostKeyChecking=no\" ${REPOSYNC_BASE_DIR}/ ${MIRROR_TARGET}:${MIRROR_REPOSYNC_BASE_DIR} "
                    mirror_result = buildlib.invoke_on_use_mirror("push.enterprise.sh")
                    if (mirror_result.contains("[FAILURE]")) {
                        echo mirror_result
                        error("Error running ${SYNC_VERSION} reposync push.enterprise.sh:\n${mirror_result}")
                    }
                }
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
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
