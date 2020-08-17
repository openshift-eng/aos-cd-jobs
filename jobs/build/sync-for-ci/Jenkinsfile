node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sync-for-ci", """
        -----------------------------------------------------------
        Sync internal repositories and images where CI can use them
        -----------------------------------------------------------
        Timing: Usually run by scheduled job several times daily per 4.y version/arch.

        This job enables CI testing to run using the same RPM repositories and
        base/builder images as production builds, to keep CI and production
        builds as close as possible and maximize the chance for CI to expose
        problems that may otherwise only be found during QE of production
        builds, if at all.

        For a given branch of ocp-build-data, repos from group.yml with
        reposync enabled are synchronized out to a private portion of the
        mirror that is only accessible with the right client certificate:
            http://mirror.openshift.com/enterprise/reposync/

        Also container images defined in streams.yml are synced out to the
        api.ci.openshift.org registry. CI tests use these repos and images for
        image builds.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '5',
                    daysToKeepStr: '5')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'GROUP',
                        description: 'The ocp-build-data group to synchronize (e.g. openshift-4.3)',
                        defaultValue: ""
                    ),
                    string(
                        name: 'REPOSYNC_DIR',
                        description: 'The directory under reposync to write to',
                        defaultValue: ""
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Architecture of repo to synchronize; must have full definition in group.yml for release',
                        choices: [ 'x86_64', 'ppc64le', 's390x' ].join("\n"),
                    ),
                    choice(
                        name: 'REPO_TYPE',
                        description: 'Type of repos to sync',
                        choices: "unsigned\nsigned",
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-reposync@redhat.com',
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )
    buildlib.initialize()

    currentBuild.displayName = "${GROUP} - ${ARCH}"
    REPOSYNC_BASE_DIR="/mnt/workspace/reposync"
    LOCAL_SYNC_DIR = "${REPOSYNC_BASE_DIR}/${REPOSYNC_DIR}"
    LOCAL_CACHE_DIR = "${REPOSYNC_BASE_DIR}_cache/${REPOSYNC_DIR}"

    MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
    MIRROR_RELATIVE_REPOSYNC = "reposync/${REPOSYNC_DIR}"
    MIRROR_ENTERPRISE_BASE_DIR = "/srv/enterprise"
    MIRROR_SYNC_DIR = "${MIRROR_ENTERPRISE_BASE_DIR}/${MIRROR_RELATIVE_REPOSYNC}"

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

                    base_args = "--working-dir ${DOOZER_WORKING} --group ${GROUP}"

                    // we need to be able to push images to api.ci, so make sure our token is fresh
                    sh "oc --kubeconfig=/home/jenkins/kubeconfigs/art-publish.kubeconfig registry login"
                    buildlib.doozer "${base_args} images:mirror-streams"

                    command = "${base_args} beta:reposync --output ${syncDir}/ --cachedir ${cacheDir}/ --repo-type ${REPO_TYPE} --arch ${ARCH}"
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
                    sh "ssh -o StrictHostKeyChecking=no ${MIRROR_TARGET} -- mkdir --mode 755 -p ${MIRROR_SYNC_DIR}"
                    sh "rsync -avzh --chmod=a+rwx,g-w,o-w --delete -e \"ssh -o StrictHostKeyChecking=no\" ${LOCAL_SYNC_DIR}/ ${MIRROR_TARGET}:${MIRROR_SYNC_DIR} "

                    timeout(time: 2, unit: 'HOURS') {
                        sh "ssh -o StrictHostKeyChecking=no ${MIRROR_TARGET} -- push.enterprise.sh -v ${MIRROR_RELATIVE_REPOSYNC}"
                    }
                }
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error syncing v${REPOSYNC_DIR} repos",
            body: """Encountered an error while running OCP pipeline: ${err}

Jenkins job: ${env.BUILD_URL}
        """);

        currentBuild.result = "FAILURE"
        throw err
    } finally {
        commonlib.safeArchiveArtifacts(["doozer_working/*.log"])
    }
}
