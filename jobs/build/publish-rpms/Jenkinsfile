#!/usr/bin/env groovy

node {
    checkout scm
    buildlib = load( "pipeline-scripts/buildlib.groovy" )
    commonlib = buildlib.commonlib
    commonlib.describeJob("publish-rpms", """
        <h2>Automatically publishing rpms to mirror</h2>
    """)

    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: ''
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'BUILD_VERSION',
                        description: 'Target release version',
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )
    commonlib.checkMock()

    version = params.BUILD_VERSION
    path = "openshift-v4/dependencies/rpms/${version}-beta"
    mirror_dir = "/srv/pub/${path}"
    commonlib.shell(
        script: """
            set -e
            ./collect-deps.sh ${version}
            rsync --recursive --delete ${version}-beta/ use-mirror-upload:${mirror_dir}
            ssh use-mirror-upload 'createrepo --database ${mirror_dir} && /usr/local/bin/push.pub.sh ${path} -v'
            rm -r ${version}-beta
        """
    )
}
