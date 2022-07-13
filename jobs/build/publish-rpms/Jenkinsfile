#!/usr/bin/env groovy

node {
    checkout scm
    buildlib = load( "pipeline-scripts/buildlib.groovy" )
    commonlib = buildlib.commonlib
    commonlib.describeJob("publish-rpms", """
        <h2>Publish RHEL 8 worker RPMs to mirror</h2>
        Creates a directory with RPMs satisfying RHEL worker nodes dependencies
        for a given 4.x release.
        For more information, see https://issues.redhat.com/browse/ART-1188 and https://issues.redhat.com/browse/ART-3695.
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

    version = params.BUILD_VERSION
    currentBuild.displayName = "$version"
    path = "openshift-v4/x86_64/dependencies/rpms"
    AWS_S3_SYNC_OPTS='--no-progress --delete'
    if (params.DRY_RUN) {
        currentBuild.displayName += " - [DRY RUN]"
        AWS_S3_SYNC_OPTS += " --dryrun"
    }
    withCredentials([aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
        commonlib.shell(
            script: """
                set -e
                python3 ./collect_deps.py --base-dir output ${version}
                aws s3 sync ${AWS_S3_SYNC_OPTS} output/${version}-el8-beta s3://art-srv-enterprise/pub/${path}/${version}-el8-beta/
                aws s3 sync ${AWS_S3_SYNC_OPTS} output/${version}-beta/ s3://art-srv-enterprise/pub/${path}/${version}-beta/
                rm -r output
            """
        )
    }
    buildlib.cleanWorkspace()
}
