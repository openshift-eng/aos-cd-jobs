node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("rebuild", """
            <h2>Rebuild an image, rpm, or RHCOS for an assembly.</h2>
            <h3>This job is used to patch one or more images with an updated RPM dependency or upstream code commit</h3>
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "",
                        artifactNumToKeepStr: "",
                        daysToKeepStr: "",
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                        commonlib.artToolsParam(),
                        string(
                            name: "ASSEMBLY",
                            description: "The name of an assembly to rebase & build for. e.g. 4.9.1",
                            trim: true
                        ),
                        choice(
                            name: 'TYPE',
                            description: 'image or rpm or rhcos',
                            choices: [
                                    'image',
                                    'rpm',
                                    'rhcos',
                                ].join('\n'),
                        ),
                        string(
                            name: "DISTGIT_KEY",
                            description: "(Optional) The name of a component to rebase & build for. e.g. openshift-enterprise-cli; leave this empty when rebuilding rhcos",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: 'OCP_BUILD_DATA_URL',
                            description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                            trim: true,
                        ),
                        booleanParam(
                            name: 'IGNORE_LOCKS',
                            description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )   // Please update README.md if modifying parameter names or semantics

        commonlib.checkMock()
        stage("initialize") {
            buildlib.registry_quay_dev_login()
            if (params.DRY_RUN) {
                currentBuild.displayName += " - [DRY RUN]"
            }
            currentBuild.displayName += " - $params.ASSEMBLY - $params.TYPE - ${params.DISTGIT_KEY?: '(N/A)'}"
        }
        stage ("Notify release channel") {
            if (params.DRY_RUN) {
                return
            }
            slackChannel = slacklib.to(params.BUILD_VERSION)
            slackChannel.say(":construction: Rebuilding $params.TYPE $params.DISTGIT_KEY for assembly $params.ASSEMBLY :construction:")
        }

        stage("rebuild") {
            sh "mkdir -p ./artcd_working"
            def cmd = [
                "artcd",
                "-vv",
                "--working-dir=./artcd_working",
                "--config", "./config/artcd.toml",
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "rebuild",
                "--ocp-build-data-url", params.OCP_BUILD_DATA_URL,
                "--version", params.BUILD_VERSION,
                "--assembly", params.ASSEMBLY,
                "--type", params.TYPE
            ]
            if (params.DISTGIT_KEY) {
                cmd << "--component"
                cmd << params.DISTGIT_KEY
            }
            if (params.IGNORE_LOCKS) {
                cmd << "--ignore-locks"
            }

            sshagent(["openshift-bot"]) {
                withCredentials([
                    string(credentialsId: 'gitlab-ocp-release-schedule-schedule', variable: 'GITLAB_TOKEN'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    usernamePassword(credentialsId: 'art-dash-db-login', passwordVariable: 'DOOZER_DB_PASSWORD', usernameVariable: 'DOOZER_DB_USER'),
                ]) {
                    echo "Will run ${cmd}"
                    wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                    }
                    withEnv([
                        "BUILD_USER_EMAIL=${builderEmail?: ''}",
                        "BUILD_URL=${BUILD_URL}",
                        "JOB_NAME=${JOB_NAME}",
                        'DOOZER_DB_NAME=art_dash'
                    ]) {
                        commonlib.shell(script: cmd.join(' '))
                    }
                }
            }
        }
        stage("operator bundle build") {
            def doozer_working = "${env.WORKSPACE}/artcd_working/doozer-working"
            def record_log = buildlib.parse_record_log(doozer_working)
            def records = record_log.get('build', [])
            def operator_nvrs = []
            for (record in records) {
                if (record["has_olm_bundle"] != '1' || record['status'] != '0' || !record["nvrs"]) {
                    continue
                }
                operator_nvrs << record["nvrs"].split(",")[0]
            }
            if (operator_nvrs != []) {  // If operator_nvrs is given but empty, we will not build bundles.
                build(job: 'build%2Folm_bundle', propagate: true, parameters: [
                    buildlib.param('String', 'BUILD_VERSION',params.BUILD_VERSION),
                    buildlib.param('String', 'ASSEMBLY', params.ASSEMBLY),
                    buildlib.param('String', 'OPERATOR_NVRS', operator_nvrs.join(",")),
                    buildlib.param('Boolean', 'DRY_RUN', params.DRY_RUN),
                ])
            }
        }
        stage("save artifacts") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/email/**",
                "artcd_working/**/*.json",
                "artcd_working/**/*.log",
            ])
        }
        stage ("Notify release channel") {
            if (params.DRY_RUN) {
                return
            }
            slackChannel = slacklib.to(params.BUILD_VERSION)
            slackChannel.say("Hi @release-artists , rebuilding $params.TYPE $params.DISTGIT_KEY for assembly $params.ASSEMBLY is done. Please check instructions in the build log for the next step.")
        }
        buildlib.cleanWorkspace()
    }
}
