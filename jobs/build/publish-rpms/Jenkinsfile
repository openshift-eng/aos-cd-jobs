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
    path = "openshift-v4/x86_64/dependencies/rpms/${version}-beta"
    mirror_dir = "/srv/pub/${path}"
    withCredentials([aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
        commonlib.shell(
            script: """
                set -e
                ./collect-deps.sh ${version}
                createrepo_c ${version}-beta -v
                rsync --recursive --delete ${version}-beta/ use-mirror-upload:${mirror_dir}
                ssh use-mirror-upload '/usr/local/bin/push.pub.sh ${path} -v'
                # Mirror to s3 as well
                aws s3 sync --no-progress --delete ${version}-beta/ s3://art-srv-enterprise/pub/${path}/
                rm -r ${version}-beta
            """
        )
    }
    buildlib.cleanWorkspace()
}
