import java.text.SimpleDateFormat

node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        def dateFormat = new SimpleDateFormat("yyyy-MMM-dd")
        def date = new Date()

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
                        string(
                            name: "NAME",
                            description: "The expected release name (e.g. 4.6.42)",
                            trim: true
                        ),
                        string(
                            name: "DATE",
                            description: "Intended release date. Format: YYYY-Mon-dd (example: 2050-Jan-01)",
                            defaultValue: "${dateFormat.format(date)}",
                            trim: true
                        ),
                        string(
                            name: "NIGHTLIES",
                            description: "(Optional for 3.y.z) list of proposed nightlies for each arch, separated by comma",
                            trim: true
                        ),
                        string(
                            name: "PACKAGE_OWNER",
                            description: "(Optional) Must be an individual email address; may be anyone who wants random advisory spam",
                            defaultValue: "lmeyer@redhat.com",
                            trim: true
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
            buildlib.initialize()
            buildlib.registry_quay_dev_login()
            def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.NAME)
            if (major >= 4 && !params.NIGHTLIES) {
                error("For OCP 4 releases, you must provide a list of proposed nightlies.")
            }
            commonlib.shell(script: "pip install -e ./pyartcd")
        }
        stage("prepare release") {
            def cmd = [
                "./pyartcd/prepare_release.py",
                "-vv",
                "--working-dir=./pyartcd_working",
                "--config=./config/artcd.toml",
                params.NAME,
                "--package-owner",
                params.PACKAGE_OWNER,
                "--date",
                params.DATE
            ]
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            if (params.PACKAGE_OWNER)
                cmd << "--package-owner" << params.PACKAGE_OWNER
            if (params.NIGHTLIES) { // unlike other languages you are familar,like Python, "".split() returns [""]
                for (nightly in params.NIGHTLIES.split("[,\\s]+")) {
                    cmd << "--nightly" << nightly.trim()
                }
            }
            sshagent(["openshift-bot"]) {
                withCredentials([usernamePassword(
                    credentialsId: 'jboss_jira_login',
                    usernameVariable: 'JIRA_USERNAME',
                    passwordVariable: 'JIRA_PASSWORD',
                )]) {
                    echo "Will run ${cmd}"
                    commonlib.shell(script: cmd.join(' '))
                }
            }
        }
        stage("save artifacts") {
            commonlib.safeArchiveArtifacts([
                "pyartcd_working/email/**",
                "pyartcd_working/**/*.json",
                "pyartcd_working/**/*.log",
            ])
        }
    }
}
