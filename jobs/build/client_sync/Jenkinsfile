#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")

    base_path = "/mnt/redhat"

    kinds = [
        "crc",
        "helm",
        "kam",
        "serverless",
        "odo",
        "rosa",
        "pipelines",
        "rhacs"
    ]

    skip_arches = [
        "none",
        "amd64",
        "ppc64le",
        "s390x",
        "arm64"
    ]

    prefixes = [
        "odo": "v",
    ]

    commonlib.describeJob("client_sync", """
        --------------------------
        Sync developer client binaries to mirror
        --------------------------
        From: https://download.eng.bos.redhat.com/
        To: https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/

        Supported clients:
        ${kinds.each { println "${it}" }}

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
                        choices: kinds.join('\n')
                    ),
                    string(
                        name: "VERSION",
                        description: "This is used to create the target directory folder name. Example: 1.24.0-0",
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: "SKIP_ARCH",
                        description: "Optional arch to be skipped, choose 'none' to sync all",
                        choices: skip_arches.join('\n')
                    ),
                    string(
                        name: "LOCATION",
                        description: "Source location relative to https://download.eng.bos.redhat.com. Example: etera/openshift-serverless-clients/1/1.7/1.7.1-2/staging",
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: "SET_LATEST",
                        description: "Try and update /latest",
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

    currentBuild.displayName = "#${currentBuild.number} - ${kind} ${params.VERSION}${(params.DRY_RUN) ? " [DRY_RUN]" : ""}"

    if (kind in ["crc", "odo", "helm"]) {
        error "${kind} is published through Content Gateway now. The mirror.openshift.com path is, under the covers, proxying the request to developers.redhat.com"
    }

    stage("Validate params") {
        if (!params.VERSION) {
            error 'SOURCE_VERSION must be specified'
        }
        if (!params.LOCATION) {
            error 'LOCATION must be specified'
        }

        dest_version = "${(kind in prefixes) ? prefixes[kind] : ""}${params.VERSION}"
        local_dest_dir = "${env.WORKSPACE}/${dest_version}"
        source_path = "${base_path}/${params.LOCATION}"
        latest_dir = "${env.WORKSPACE}/latest/"
        
        if (kind == "rhacs") {
            if (params.SET_LATEST) {
                error 'SET_LATEST is not supported for rhacs'
            }
            s3_target_dir = "/pub/rhacs/support-packages/${dest_version}"
        } else {
            s3_target_dir = "/pub/openshift-v4/x86_64/clients/${kind}/${dest_version}/"
        }
        
        echo "destination version: ${dest_version}"
        echo "source path: ${source_path}"
        echo "latest dir: ${latest_dir}"
        echo "s3 target dir: ${s3_target_dir}"
        
        if (params.SET_LATEST) {
            s3_latest_dir = "/pub/openshift-v4/x86_64/clients/${kind}/latest/"
            echo "s3 latest dir: ${s3_latest_dir}"
        }
    }

    stage("Clean working dir") {
        sh "rm -rf ${local_dest_dir}"
    }

    stage("Sync to mirror") {
        if (params.LOCATION.startsWith("rcm-guest")) {
            source_path = "${params.LOCATION.substring(10)}/"
            commonlib.shell(
                script:
                """
                set -euxo pipefail
                mkdir -p ${local_dest_dir}
                rsync -rlp --info=progress2 exd-ocp-buildvm-bot-prod@spmm-util:${source_path} ${local_dest_dir}
                """
            )
        } else {
            // Copy NFS dir to local tmp dir
            commonlib.shell(
                script:
                """
                set -euxo pipefail
                cp -aL ${source_path} ${local_dest_dir}
                if [ -e ${local_dest_dir}/sha256sum.txt ]; then
                    cat ${local_dest_dir}/sha256sum.txt
                fi
                """
            )
        }

        // Remove undesired arch from source dir
        if (params.SKIP_ARCH != "none") {
            commonlib.shell(
                script:
                """
                rm -f ${local_dest_dir}/*${params.SKIP_ARCH}*
                tree ${local_dest_dir}
                """
            )
        }

        if (params.DRY_RUN) {
            echo "Would have s3 sync'ed ${dest_version} to ${s3_target_dir}"
        } else {
            commonlib.syncDirToS3Mirror(dest_version, s3_target_dir)
        }

        if (params.SET_LATEST) {
            commonlib.shell(
                script:
                """
                set -euxo pipefail
                rm -rf ${latest_dir}
                cp -aL ${local_dest_dir} ${latest_dir}
                """
            )

            if (params.DRY_RUN) {
                println("Would have s3 sync'ed ${latest_dir} to ${s3_latest_dir}")
            } else {
                commonlib.syncDirToS3Mirror(latest_dir, s3_latest_dir)
            }
        }
    }
}
