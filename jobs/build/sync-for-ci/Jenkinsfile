node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sync-for-ci", """
        <h2>Sync internal repositories and images where CI can use them</h2>
        </b>Timing</b>: Usually run by scheduled job several times daily per 4.y version/arch.

        This job enables CI testing to run using the same RPM repositories and
        base/builder images as production builds, to keep CI and production
        builds as close as possible and maximize the chance for CI to expose
        problems that may otherwise only be found during QE of production
        builds, if at all.

        For a given branch of ocp-build-data, repos from group.yml with
        reposync enabled are synchronized out to a private portion of the
        mirror that is only accessible with the right client certificate:
            <a href="http://mirror.openshift.com/enterprise/reposync/" target="_blank">http://mirror.openshift.com/enterprise/reposync/</a>

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
                    commonlib.doozerParam(),
                    string(
                        name: 'GROUP',
                        description: 'The ocp-build-data group to synchronize (e.g. openshift-4.3)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'REPOSYNC_DIR',
                        description: 'The directory under reposync to write to',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Architecture of repo to synchronize; must have full definition in group.yml for release',
                        choices: commonlib.brewArches,
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
                        ].join(','),
                        trim: true,
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
    MIRROR_TARGET = "use-mirror-upload.ops.rhcloud.com"
    MIRROR_RELATIVE_REPOSYNC = "reposync/${REPOSYNC_DIR}"

    if ( ARCH != 'x86_64' ) {
        // Non x86_64 arch directories will have the arch as a suffix
        LOCAL_SYNC_DIR = "${LOCAL_SYNC_DIR}_${ARCH}"
        MIRROR_RELATIVE_REPOSYNC = "${MIRROR_RELATIVE_REPOSYNC}_${ARCH}"
    }

    LOCAL_CACHE_DIR = "${REPOSYNC_BASE_DIR}_cache/${REPOSYNC_DIR}_${ARCH}"
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
                    base_args = "--working-dir ${DOOZER_WORKING} --group ${GROUP}"
                    // Specify -a ${ARCH} to allow repos to be constructed for the arch even if
                    // if it is not enabled in group.yml.
                    command = "${base_args} -a ${ARCH} beta:reposync --output ${LOCAL_SYNC_DIR}/ --cachedir ${LOCAL_CACHE_DIR}/ --repo-type ${REPO_TYPE} --arch ${ARCH}"
                    buildlib.doozer command

                    /**
                     * A bug in doozer once caused only noarch RPMs to be synced to the mirrors. Prevent this
                     * by making sure a minimum number of arch-specific RPMs actually exist locally before
                     * pushing the updated content to the mirrors.
                     */

                    sanityCheckRes = commonlib.shell(
                            returnAll: true,
                            script: "find ${LOCAL_SYNC_DIR} -name '*.${ARCH}.rpm' | wc -l"
                    )

                    if(sanityCheckRes.stdout.trim().toInteger() < 50){
                        error("Did not find a sufficient number of arch specific RPMs; human checks required!")
                    }

                }

                stage("push to mirror") {
                    sh "ssh -o StrictHostKeyChecking=no ${MIRROR_TARGET} -- mkdir --mode 755 -p ${MIRROR_SYNC_DIR}"
                    sh "rsync -avzh --copy-links --chmod=a+rwx,g-w,o-w --delete -e \"ssh -o StrictHostKeyChecking=no\" ${LOCAL_SYNC_DIR}/ ${MIRROR_TARGET}:${MIRROR_SYNC_DIR} "

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
