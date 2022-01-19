#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("tarball-sources", """
        <h2>Prepare container-first tarball sources for publishing</h2>
        <b>Timing</b>: After the release job has run. See:
        <a href="https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#provide-non-golang-container-first-sources-to-rcm" target="_blank">the docs</a>

        We have a legal requirement to publish the sources of all our builds.
        Containers which are built from source are mostly golang and handled by
        automation. Those which are not need to be published manually by EXD.
        This job prepares those sources so that EXD can publish them.
    """)


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
                    commonlib.ocpVersionParam('VERSION'),
                    string(
                        name: "ASSEMBLY",
                        description: "The name of an assembly; must be defined in releases.yml (e.g. 4.9.1)",
                        defaultValue: "stream",
                        trim: true
                    ),
                    string(
                        name: 'ADVISORY',
                        description: '(Optional) Image release advisory number. Leave empty to load from ocp-build-data.',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(','),
                        trim: true,
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
    )

    commonlib.checkMock()
    buildlib.initialize()
    commonlib.shell(script: "pip install -e ./pyartcd")

    try {
        sshagent(['openshift-bot']) {
            currentBuild.description = "OCP ${params.VERSION} - ${params.ASSEMBLY}"
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0

            def output = ""

            stage("run tarball-sources") {
                sh "rm -rf ./artcd_working"
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
                    "tarball-sources",
                    "--group", "openshift-${params.VERSION}",
                    "--assembly", params.ASSEMBLY,
                ]
                if (advisory) {
                    cmd << "--advisory" << "${advisory}"
                }
                if (params.DEFAULT_ADVISORIES) {
                    cmd << "--default-advisories"
                }
                sshagent(["openshift-bot"]) {
                    withCredentials([string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                        echo "Will run ${cmd}"
                        output = commonlib.shell(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }

            stage("slack notification to release channel") {
                def jiraKey = (output =~ /CLOUDDST-\d+/)[0]
                jiraCardURL = "https://issues.redhat.com/browse/${jiraKey}"

                slacklib.to(version).say("""
                *:white_check_mark: tarball-sources sent to CLOUDDST*
CLOUDDST JIRA: ${jiraCardURL}
buildvm job:   ${commonlib.buildURL('console')}
                """)
            }
        }

    } catch (err) {
        slacklib.to(version).say("""
        *:heavy_exclamation_mark: @release-artists tarball-sources failed*
        buildvm job: ${commonlib.buildURL('console')}
        """)

        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Tarball sources",
            body: "Encountered an error while running OCP Tarball sources: ${err}");
        currentBuild.description = "Error while running OCP Tarball sources:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    } finally {
        buildlib.cleanWorkspace()
    }

}
