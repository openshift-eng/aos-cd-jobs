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
                    target_version = params.TKN_VERSION.split("-")[0]
                    target_dir = "/srv/pub/openshift-v4/x86_64/clients/pipeline/${target_version}"
                    s3_target_dir = "/pub/openshift-v4/x86_64/clients/pipeline/${target_version}"
                }
            }
        }

        stage('Sync to mirror') {
            steps {
                script {
                    sh "tree /mnt/redhat/staging-cds/developer/openshift-pipelines-client/${params.TKN_VERSION}/staging ; cat /mnt/redhat/staging-cds/developer/openshift-pipelines-client/${params.TKN_VERSION}/staging/sha256sum.txt"
                    commonlib.syncDirToS3Mirror("/mnt/redhat/staging-cds/developer/openshift-pipelines-client/${params.TKN_VERSION}/staging/", "${s3_target_dir}/" )
                    commonlib.syncDirToS3Mirror("/mnt/redhat/staging-cds/developer/openshift-pipelines-client/${params.TKN_VERSION}/staging/", "/pub/openshift-v4/x86_64/clients/pipeline/latest/" )
                }
            }
        }
    }
}

def download(url) {
    sh "wget --directory-prefix ${params.TKN_VERSION} ${url}"
}
