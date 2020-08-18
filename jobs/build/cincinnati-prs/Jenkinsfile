#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def commonlib = release.commonlib
    commonlib.describeJob("cincinnati-prs", """
        --------------------------------------------------
        Create the PRs for Cincinnati to publish a release
        --------------------------------------------------
        Timing: The "release" job runs this once the release is accepted.
        
        This creates PRs to enter the new release in all the relevant Cincinnati channels.
        (updates https://github.com/openshift/cincinnati-graph-data/tree/master/channels)

        For more details see the README:
        https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/cincinnati-prs/README.md
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
                        name: 'RELEASE_NAME',
                        description: 'The name of the release to add to Cincinnati via PRs',
                        defaultValue: ""
                    ),
                    string(
                        name: 'ADVISORY_NUM',
                        description: 'Internal advisory number for release (i.e. https://errata.devel.redhat.com/advisory/??????)',
                        defaultValue: ""
                    ),
                    booleanParam(
                        name: 'CANDIDATE_CHANNEL_ONLY',
                        description: 'Only open a PR for the candidate channel',
                        defaultValue: false
                    ),
                    string(
                        name: 'GITHUB_ORG',
                        description: 'The github org containing cincinnati-graph-data fork to open PRs against (use for testing)',
                        defaultValue: "openshift"
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
        release.openCincinnatiPRs(params.RELEASE_NAME.trim(), params.ADVISORY_NUM.trim(), params.CANDIDATE_CHANNEL_ONLY, params.GITHUB_ORG.trim(), params.SKIP_OTA_SLACK_NOTIFICATION)
    }
    buildlib.cleanWorkdir(workdir)
}
