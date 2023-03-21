#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")

    location = [
        "crc": "/mnt/redhat/staging-cds/developer/crc/%s/staging/",
        "helm": "/mnt/redhat/staging-cds/developer/helm/%s/staging/",
        "kam": "/mnt/redhat/staging-cds/developer/openshift-gitops-kam/%s/staging/",
        "serverless": "/mnt/redhat/staging-cds/developer/openshift-serverless-clients/%s/staging/",
        "odo": "/mnt/redhat/staging-cds/developer/odo/%s/staging/",
        "rosa": "/mnt/redhat/staging-cds/etera/rosa/%s/staging/",
        "pipelines": "/mnt/redhat/staging-cds/developer/openshift-pipeline-clients/%s/staging/",
    ]

    prefixes = [
        "odo": "v",
    ]

    commonlib.describeJob("client_sync", """
        --------------------------
        Sync developer client binaries to mirror
        --------------------------
        From: https://download.eng.bos.redhat.com/staging-cds/developer/
        To: http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/

        Supported clients:
        ${location.keySet().each { println "${it}" }}

        Timing: This is only ever run by humans, upon request.
    """)

    properties(
        [
            disableResume(), 
            buildDiscarder(logRotator(artifactDaysToKeepStr: '30', daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: "KIND",
                        description: "What binary type to sync",
                        choices: location.keySet().join('\n')
                    ),
                    string(
                        name: "SOURCE_VERSION",
                        description: "This should exactly match the source directory version folder to fetch from. Also used to create the target directory folder name. If OVERRIDE_LOCATION is used then only used for target directory name. Example: 1.24.0-0",
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: "OVERRIDE_LOCATION",
                        description: "Warning: This overrides the SOURCE_VERSION and default location. Example: /mnt/redhat/staging-cds/etera/openshift-gitops-kam/1/1.8/1.8.0-143/staging" ,
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: "SET_LATEST",
                        description: "Update /latest",
                        defaultValue: true,
                    ),
                    booleanParam(
                        name: "DRY_RUN",
                        description: "Run without updating mirror",
                        defaultValue: false,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    def kind = params.KIND
    def source_version = params.SOURCE_VERSION

    currentBuild.displayName = "#${currentBuild.number} - ${kind} ${source_version}${(params.DRY_RUN) ? " [DRY_RUN]" : ""}"

    stage("Validate params") {
        if (!source_version) {
            error 'SOURCE_VERSION must be specified'
        }
        dest_version = "${(kind in prefixes) ? prefixes[kind] : ""}${source_version}"
        source_dir = params.OVERRIDE_LOCATION ? params.OVERRIDE_LOCATION : String.format(location[kind], source_version)
        latest_dir = "latest/"
    }

    stage("Sync to mirror") {
        s3_target_dir = "/pub/openshift-v4/x86_64/clients/${kind}/${dest_version}/"
        commonlib.shell([
            "set -euxo pipefail",
            "tree ${source_dir}",
            "cat ${source_dir}/sha256sum.txt"
        ].join('\n'))
        println("params.DRY_RUN: ${params.DRY_RUN}")
        if (params.DRY_RUN) {
            println("Would have s3 sync'ed ${source_dir} to ${s3_target_dir}")
        } else {
            commonlib.syncDirToS3Mirror(source_dir, s3_target_dir)
        }

        if (params.SET_LATEST) {
            s3_latest_dir = "/pub/openshift-v4/x86_64/clients/${kind}/latest/"
            commonlib.shell([
                "set -euxo pipefail",
                "rm -rf ${latest_dir}",
                "cp -aL ${source_dir} ${latest_dir}",
            ].join('\n'))
            if (params.DRY_RUN) {
                println("Would have s3 sync'ed ${latest_dir} to ${s3_latest_dir}")
            } else {
                commonlib.syncDirToS3Mirror(latest_dir, s3_latest_dir)
            }
        }
    }
}
