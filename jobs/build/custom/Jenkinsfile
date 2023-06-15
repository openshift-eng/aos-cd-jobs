node {
    checkout scm

    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("custom", """
        <h2>Run component builds in ways other jobs can't</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.

        This job is mainly used when you need something specific not handled
        well by the ocp3 or ocp4 jobs and don't want to set up and use doozer.

        It is also still necessary for building OCP 3.11 releases using signed
        RPMs in containers.

        For more details see the <a href="https://github.com/openshift-eng/aos-cd-jobs/blob/master/jobs/build/custom/README.md" target="_blank">README</a>
    """)


    // Please update README.md if modifying parameter names or semantics
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '365',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    commonlib.doozerParam(),
                    booleanParam(
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        defaultValue: false
                    ),
                    string(
                        name: 'VERSION',
                        description: '(Optional) version for build (e.g. 4.3.42) instead of most recent\nor "+" to bump most recent version',
                        trim: true,
                    ),
                    string(
                        name: 'RELEASE',
                        description: '(Optional) Release string for build instead of default (1 for 3.x, timestamp.p? for 4.x)',
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to rebase & build for. If assemblies are not enabled in group.yml, this parameter will be ignored',
                        defaultValue: "test",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'RPMS',
                        description: 'List of RPM distgits to build. Empty for all. Enter "NONE" to not build any.',
                        defaultValue: "NONE",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'UPDATE_REPOS',
                        description: 'Build plashets (always true if building RPMs or images for non-stream assembly)',
                        defaultValue: false,
                    ),
                    string(
                        name: 'IMAGES',
                        description: 'List of image distgits to build. Empty for all. Enter "NONE" to not build any.',
                        trim: true,
                    ),
                    string(
                        name: 'EXCLUDE_IMAGES',
                        description: 'List of image distgits NOT to build (builds all not listed - IMAGES value is ignored)',
                        trim: true
                    ),
                    choice(
                        name: 'IMAGE_MODE',
                        description: 'How to update image dist-gits: with a source rebase, or not at all (re-run as-is)',
                        choices: ['rebase', 'nothing'].join('\n'),
                    ),
                    booleanParam(
                        name: 'SCRATCH',
                        description: 'Run scratch builds (only unrelated images, no children)',
                        defaultValue: false,
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-custom-build@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )   // Please update README.md if modifying parameter names or semantics
    commonlib.checkMock()
    buildlib.initialize(false, params.BUILD_VERSION == "3.11")

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${env.WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    def (majorVersion, minorVersion) = commonlib.extractMajorMinorVersionNumbers(params.BUILD_VERSION)
    def groupParam = "openshift-${params.BUILD_VERSION}"
    def doozer_data_gitref = params.DOOZER_DATA_GITREF
    if (doozer_data_gitref) {
        groupParam += "@${params.DOOZER_DATA_GITREF}"
    }
    def doozerOpts = "--working-dir ${doozer_working} --data-path ${params.DOOZER_DATA_PATH} --group '${groupParam}' "
    def version = params.BUILD_VERSION
    def release = "?"
    if (params.IMAGE_MODE != "nothing") {
        version = params.BUILD_VERSION.trim()
        release = params.RELEASE.trim() ?: buildlib.defaultReleaseFor(params.BUILD_VERSION)
    }
    // If any arch is ready for GA, use signed repos for all (plashets will sign everything).
    def out = buildlib.doozer("--group=openshift-${params.BUILD_VERSION} config:read-group --yaml release_state",
                                [capture: true]).trim()
    def archReleaseStates = readYaml(text: out)
    echo "arch release state for ${params.BUILD_VERSION}: ${archReleaseStates}"
    def repo_type = archReleaseStates['release'] ? 'signed' : 'unsigned'

    def images = commonlib.cleanCommaList(params.IMAGES)
    def exclude_images = commonlib.cleanCommaList(params.EXCLUDE_IMAGES)
    def rpms = commonlib.cleanCommaList(params.RPMS)

    if (params.ASSEMBLY && params.ASSEMBLY != 'stream' && buildlib.doozer("${doozerOpts} config:read-group --default=False assemblies.enabled", [capture: true]).trim() != 'True') {
        error("ASSEMBLY cannot be set to '${params.ASSEMBLY}' because assemblies are not enabled in ocp-build-data.")
    }

    currentBuild.displayName = "#${currentBuild.number} - ${version}-${release}"

    try {
        sshagent(["openshift-bot"]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot
            currentBuild.description = ""

            stage("rpm builds") {
                if (rpms.toUpperCase() == "NONE") {
                    return
                }
                currentBuild.displayName += rpms.contains(",") ? " [RPMs]" : " [${rpms} RPM]"
                currentBuild.description = "building RPM(s): ${rpms}\n"

                sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                def cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=./artcd_working",
                    "--config=./config/artcd.toml",
                    "custom",
                    "build-rpms",
                    "--version=${version}-${release}",
                    "--assembly=${params.ASSEMBLY}",
                ]
                if (rpms) {
                    cmd << "--rpms=${rpms}"
                }
                cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                if (params.DOOZER_DATA_GITREF) {
                    cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
                }
                if (params.SCRATCH) {
                    cmd << "--scratch"
                }

                params.IGNORE_LOCKS ?  sh(script: cmd.join(' ')) : lock("github-activity-lock-${params.BUILD_VERSION}") { sh(script: cmd.join(' ')) }
            }

            stage("repo: ose 'building'") {
                if (params.UPDATE_REPOS || (images.toUpperCase() != "NONE" && params.ASSEMBLY && params.ASSEMBLY != 'stream') || rpms.toUpperCase() != "NONE") {
                    sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                    def cmd = [
                        "artcd",
                        "-v",
                        "--working-dir=./artcd_working",
                        "--config=./config/artcd.toml",
                        "custom",
                        "update-repos",
                        "--version=${version}-${release}",
                        "--assembly=${params.ASSEMBLY}",
                    ]
                    if (params.DOOZER_DATA_PATH) {
                        cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                    }
                    if (params.DOOZER_DATA_GITREF) {
                        cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
                    }

                    withCredentials([
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                            string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                            string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                            string(credentialsId: 'redis-port', variable: 'REDIS_PORT')
                        ]) {
                        sh(script: cmd.join(' '))
                    }
                }
            }

            stage('build images') {
                if (exclude_images) {
                    currentBuild.displayName += " [images]"
                    currentBuild.description += "building all images except: ${exclude_images}"
                }
                else if (images == "") {
                    currentBuild.displayName += " [images]"
                    currentBuild.description += "building all images"
                }
                else if (images != "NONE") {
                    currentBuild.displayName += images.contains(",") ? " [images]" : " [${images} image]"
                    currentBuild.description += "building image(s): ${images}"
                }

                sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                cmd = [
                        "artcd",
                        "-v",
                        "--working-dir=./artcd_working",
                        "--config=./config/artcd.toml",
                        "custom",
                        "build-images",
                        "--version=${version}-${release}",
                        "--assembly=${params.ASSEMBLY}",
                ]
                if (params.DOOZER_DATA_PATH) {
                    cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                }
                if (params.DOOZER_DATA_GITREF) {
                    cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
                }
                cmd << "--images=${images}"
                if (exclude_images) {
                    cmd << "--exclude=${exclude_images}"
                }
                cmd << "--image-mode=${params.IMAGE_MODE}"
                if (params.SCRATCH) {
                    cmd << "--scratch"
                }

                withCredentials([string(credentialsId: 'gitlab-ocp-release-schedule-schedule', variable: 'GITLAB_TOKEN')]) {
                    try {
                        params.IGNORE_LOCKS ?  sh(script: cmd.join(' ')) : lock("github-activity-lock-${params.BUILD_VERSION}") { sh(script: cmd.join(' ')) }
                    } catch (err) {
                        def record_log = buildlib.parse_record_log(doozer_working)
                        def failed_map = buildlib.get_failed_builds(record_log, true)
                        if (failed_map) {
                            def r = buildlib.determine_build_failure_ratio(record_log)
                            if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
                                echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
                            } else {
                                buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
                            }
                        }
                        throw err  // build is considered failed if anything failed
                    }
                }
            }

            stage('sync images') {
                if (params.SCRATCH || (!exclude_images && images.toUpperCase() == "NONE")) { return }  // no point
                
                sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"

                cmd = [
                        "artcd",
                        "-v",
                        "--working-dir=./artcd_working",
                        "--config=./config/artcd.toml",
                        "custom",
                        "sync-images",
                        "--version=${version}",
                        "--assembly=${params.ASSEMBLY}",
                        "--data-path=${params.DOOZER_DATA_PATH}",
                        "--data-gitref=${params.DOOZER_DATA_GITREF}"
                ]

                try {
                    withCredentials([string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'), string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN')]) {
                        withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                            sh(script: cmd.join(' '))
                        }
                    }
                } catch(err) {
                    commonlib.email(
                        replyTo: params.MAIL_LIST_FAILURE,
                        to: "aos-art-automation+failed-image-sync@redhat.com",
                        from: "aos-art-automation@redhat.com",
                        subject: "Problem syncing images after ${currentBuild.displayName}",
                        body: "Jenkins console: ${commonlib.buildURL('console')}",
                    )
                }
            }

            if (params.MAIL_LIST_SUCCESS.trim()) {
                commonlib.email(
                    to: params.MAIL_LIST_SUCCESS,
                    from: "aos-team-art@redhat.com",
                    subject: "Successful custom OCP build: ${currentBuild.displayName}",
                    body: "Jenkins job: ${commonlib.buildURL()}\n${currentBuild.description}",
                )
            }
        }
    } catch (err) {
        currentBuild.description += "\nerror: ${err.getMessage()}"
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Error building custom OCP: ${currentBuild.displayName}",
            body: """Encountered an error while running OCP pipeline:

${currentBuild.description}

Jenkins job: ${commonlib.buildURL()}
Job console: ${commonlib.buildURL('console')}
    """)

        currentBuild.result = "FAILURE"
        throw err
    } finally {
        commonlib.compressBrewLogs()
        commonlib.safeArchiveArtifacts([
                "doozer_working/*.log",
                "doozer_working/*.yaml",
                "doozer_working/brew-logs/**",
            ])
        buildlib.cleanWorkdir(doozer_working)
        buildlib.cleanWorkspace()
    }
}
