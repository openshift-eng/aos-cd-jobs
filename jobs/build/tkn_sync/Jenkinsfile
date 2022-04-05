#!/usr/bin/env groovy

node {
    checkout scm
    commonlib = load('pipeline-scripts/commonlib.groovy')
    commonlib.describeJob("tkn_sync", """
        -----------------------------------------------
        Sync the Tekton pipeline client (tkn) to mirror
        -----------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/pipeline/
        Timing: Run manually by request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: 'TKN_VERSION',
            description: 'Example: 1.3.1-1',
            defaultValue: '',
            trim: true,
        )
    }

    stages {
        stage('Validate params') {
            steps {
                script {
                    if (!params.TKN_VERSION) {
                        error 'TKN_VERSION must be specified'
                    }
                    version = params.TKN_VERSION
                    short_version = params.TKN_VERSION.split("-")[0]
                    source_dir = "/mnt/redhat/staging-cds/developer/openshift-pipelines-client/${version}/staging/"
                    latest_dir = "latest"
                }
            }
        }

        stage('Sync to mirror') {
            steps {
                script {
                    s3_target_dir = "/pub/openshift-v4/x86_64/clients/pipeline/${short_version}/"
                    s3_latest_dir = "/pub/openshift-v4/x86_64/clients/pipeline/latest/"
                    commonlib.shell("""
                        set -euxo pipefail
                        tree ${source_dir}
                        cat ${source_dir}/sha256sum.txt
                        rm -rf ${latest_dir}
                        cp -a ${source_dir} ${latest_dir}
                        # make names that are not version specific
                        for file in ${latest_dir}/*-${short_version}*; do
                            cp -a "\${file}" "\${file/-${short_version}/}"
                        done
                    """)
                    commonlib.syncDirToS3Mirror(source_dir, s3_target_dir)
                    commonlib.syncDirToS3Mirror(latest_dir, s3_latest_dir)
                }
            }
        }
    }
}

def download(url) {
    sh "wget --directory-prefix ${params.TKN_VERSION} ${url}"
}
