#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("set_client_latest", """
        --------------------------------------------------
        Update "latest" symlinks for published ocp clients
        --------------------------------------------------
        Timing: Run by scheduled-builds/set_cincinnati_links which runs every 10 minutes.

        This job looks at what has been published in the various cincinnati
        channels and updates the symlinks accordingly under 
        http://mirror.openshift.com/pub/openshift-v4/<arch>/clients/ocp

        try.openshift.com directs customers to "latest" links, so they need to
        be kept in sync with what has been made available in cincinnati.
    """)


    // Expose properties for a parameterized build
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
                        name: 'CHANNEL_OR_RELEASE',
                        description: 'Pull latest from named channel (e.g. stable-4.3) or set to specific dir (e.g. 4.1.0)',
                        defaultValue: ""
                    ),
                    string(
                        name: 'CLIENT_TYPE',
                        description: 'artifacts path of https://mirror.openshift.com (i.e. ocp, ocp-dev-preview)',
                        defaultValue: "ocp"
                    ),
                    choice(
                        name: 'LINK_NAME',
                        description: 'The name of the links to establish. Specifying "latest" will establish a "latest-4.X" link for the release and potentially an overall "latest". "stable" will make a corresponding set of "stable-4.x" and "stable" links.',
                        choices: ['latest', 'stable', 'fast', 'candidate'].join('\n'),
                    ),
                    string(
                        name: 'ARCHES',
                        description: 'all, any, or a space delimited list of arches: "x86_64 s390x ..."',
                        defaultValue: "all"
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-setting-client-latest@redhat.com'
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()



    try {
        currentBuild.displayName = "#${currentBuild.number} - ${CHANNEL_OR_RELEASE} (arches: ${ARCHES})"

        if ( params.CLIENT_TYPE == "ocp" &&  params.CHANNEL_OR_RELEASE.charAt(0).isDigit() ) {
            // For released ocp clients, only support channel names.
            error("Released ocp client links are managed automatically by polling Cincinnati. See set_cincinnati_links in scheduled-jobs")
        }

        timeout(15) {
            result = buildlib.invoke_on_use_mirror("set-v4-client-latest.sh", params.CHANNEL_OR_RELEASE, params.CLIENT_TYPE, params.LINK_NAME, params.ARCHES)
        }
        echo "${result}"
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-cicd@redhat.com",
            subject: "Error setting latest ocp client",
            body: "Encountered an error while setting latest ocp client: ${err}");
        currentBuild.description = "Error while setting latest ocp client:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
    buildlib.cleanWorkdir("${env.WORKSPACE}")
}
