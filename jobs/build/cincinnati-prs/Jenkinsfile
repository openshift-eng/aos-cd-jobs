#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def commonlib = release.commonlib
    commonlib.describeJob("cincinnati-prs", """
        <hr />
        <h2>Create the PRs for Cincinnati to publish a release</h2>
        <hr />
        <p><b>Timing</b>: The "release" job runs this once the release is accepted.</p>
        This creates PRs to enter the new release in all the relevant Cincinnati channels <a href="https://github.com/openshift/cincinnati-graph-data/tree/master/channels" target="_blank">here</a>
        <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/cincinnati-prs/README.md">For more details see the README.</a>
    """)

    // Please update README.md if modifying parameter names or semantics
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '500')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Nightly from which the release was derived (only used for Slack notification)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'RELEASE_NAME',
                        description: 'The name of the release to add to Cincinnati via PRs',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ADVISORY_NUM',
                        description: 'Internal advisory number for release (i.e. https://errata.devel.redhat.com/advisory/??????)',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'CANDIDATE_CHANNEL_ONLY',
                        description: 'Only open a PR for the candidate channel',
                        defaultValue: false
                    ),
                    string(
                        name: 'GITHUB_ORG',
                        description: 'The github org containing cincinnati-graph-data fork to open PRs against (use for testing)',
                        defaultValue: "openshift",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'SKIP_OTA_SLACK_NOTIFICATION',
                        description: 'Do not notify OTA team',
                        defaultValue: false
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )   // Please update README.md if modifying parameter names or semantics

    commonlib.checkMock()
    workdir = "${env.WORKSPACE}/workdir"
    buildlib.cleanWorkdir(workdir, true)
    currentBuild.displayName = params.RELEASE_NAME
    currentBuild.description = ""
    dir(workdir) {
        def releaseName = params.RELEASE_NAME.trim()
        def ghorg = params.GITHUB_ORG.trim()
        def noSlackOutput = params.SKIP_OTA_SLACK_NOTIFICATION
        def prs = release.openCincinnatiPRs(releaseName, params.ADVISORY_NUM.trim(), params.CANDIDATE_CHANNEL_ONLY, ghorg)
        if ( prs ) {  // did we open any?
            release.sendCincinnatiPRsSlackNotification(releaseName, params.FROM_RELEASE_TAG.trim(), prs, ghorg, noSlackOutput)
        }

    }
    buildlib.cleanWorkdir(workdir)
    buildlib.cleanWorkspace()
}
