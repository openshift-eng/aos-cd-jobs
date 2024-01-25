import java.text.SimpleDateFormat

node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("prepare-release", """
            <h2>This job will perform an assortment of release tasks for creating a release from scratch.</h2>
            <b>Timing</b>: On the prepare-the-release day (Monday).
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
                        commonlib.ocpVersionParam('VERSION'),
                        commonlib.artToolsParam(),
                        string(
                            name: "ASSEMBLY",
                            description: "The name of an assembly; must be defined in releases.yml (e.g. 4.9.1)",
                            defaultValue: "stream",
                            trim: true
                        ),
                        string(
                            name: "NAME",
                            description: "The expected release name (e.g. 4.6.42); Do not specify for a non-stream assembly.",
                            trim: true
                        ),
                        string(
                            name: "DATE",
                            description: "(Optional) Leave empty to use auto-fetched release date. Intended release date. Format: YYYY-Mon-dd (example: 2050-Jan-01)",
                            trim: true
                        ),
                        string(
                            name: "NIGHTLIES",
                            description: "(Optional for 3.y.z) list of proposed nightlies for each arch, separated by comma; Do not specify for a non-stream assembly (nightlies should be in releases.yml)",
                            trim: true
                        ),
                        string(
                            name: "PACKAGE_OWNER",
                            description: "(Optional) Must be an individual email address; may be anyone who wants random advisory spam",
                            defaultValue: "lmeyer@redhat.com",
                            trim: true
                        ),
                        booleanParam(
                            name: "DEFAULT_ADVISORIES",
                            description: "Do not create advisories/jira; pick them up from ocp-build-data; Do not specify for a non-stream assembly (advisories should be in releases.yml)",
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "INCLUDE_SHIPPED",
                            description: "Do not filter our shipped builds, attach all builds to advisory.(Used at pre-GA time)",
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
            if (params.ASSEMBLY == "stream") {
                def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.NAME)
                currentBuild.displayName += " - $params.NAME"
                if (major >= 4 && !params.NIGHTLIES) {
                    error("For OCP 4 releases, you must provide a list of proposed nightlies.")
                }
            } else {
                if (params.NAME) {
                    error("NAME must not be specified if ASSEMBLY is not 'stream'.")
                }
                currentBuild.displayName += " - $params.VERSION - $params.ASSEMBLY"
            }
        }
        try {
            stage("prepare release") {
                sh "mkdir -p ./artcd_working"
                def cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=./artcd_working",
                    "--config", "./config/artcd.toml",
                ]
                if (params.DRY_RUN) {
                    cmd << "--dry-run"
                }
                cmd += [
                    "prepare-release",
                    "--group", "openshift-${params.VERSION}",
                    "--assembly", params.ASSEMBLY,
                ]
                if (params.DATE) {
                    cmd << "--date" << params.DATE
                }
                if (params.NAME) {
                    cmd << "--name" << params.NAME
                }
                if (params.DEFAULT_ADVISORIES) {
                    cmd << "--default-advisories"
                }
                if (params.INCLUDE_SHIPPED) {
                    cmd << "--include-shipped"
                }
                if (params.PACKAGE_OWNER)
                    cmd << "--package-owner" << params.PACKAGE_OWNER
                if (params.NIGHTLIES) { // unlike other languages you are familar,like Python, "".split() returns [""]
                    for (nightly in params.NIGHTLIES.split("[,\\s]+")) {
                        cmd << "--nightly" << nightly.trim()
                    }
                }
                sshagent(["openshift-bot"]) {
                    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'), string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                        echo "Will run ${cmd}"
                        commonlib.shell(script: cmd.join(' '))
                    }
                }
            }
        } catch (err) {
            currentBuild.result = "FAILURE"
            throw err
        } finally {
            commonlib.safeArchiveArtifacts([
                "artcd_working/email/**",
                "artcd_working/**/*.json",
                "artcd_working/**/*.log",
                "artcd_working/**/*.yaml",
                "artcd_working/**/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }
}
