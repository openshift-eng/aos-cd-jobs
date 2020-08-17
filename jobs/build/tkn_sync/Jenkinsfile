#!/usr/bin/env groovy

node {
    load('pipeline-scripts/commonlib.groovy').describeJob("tkn_sync", """
        -----------------------------------------------
        Sync the Tekton pipeline client (tkn) to mirror
        -----------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/pipeline/
        Timing: Run manually by request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: 'TKN_VERSION',
            description: 'Example: 0.9.0',
            defaultValue: ''
        )
        string(
            name: 'TKN_URL',
            description: 'Example: http://download.eng.bos.redhat.com/staging-cds/developer/openshift-pipelines-client/0.9.0-2',
            defaultValue: ''
        )
    }

    stages {
        stage('Validate params') {
            steps {
                script {
                    if (!params.TKN_VERSION) {
                        error 'TKN_VERSION must be specified'
                    }
                    if (!params.TKN_URL) {
                        error 'TKN_URL must be specified'
                    }
                }
            }
        }
        stage('Download Artifacts') {
            steps {
                sh "rm -rf ${params.TKN_VERSION}"
                sh "mkdir -p ${params.TKN_VERSION}/{linux,macos,windows}"

                sh "wget -nv ${params.TKN_URL}/signed/linux/tkn-linux-amd64 -O ${params.TKN_VERSION}/linux/tkn"
                sh "wget -nv ${params.TKN_URL}/signed/macos/tkn-darwin-amd64 -O ${params.TKN_VERSION}/macos/tkn"
                sh "wget -nv ${params.TKN_URL}/signed/windows/tkn-windows-amd64.exe -O ${params.TKN_VERSION}/windows/tkn.exe"
                sh "wget -nv ${params.TKN_URL}/rpm/usr/share/licenses/openshift-pipelines-client-redistributable/LICENSE -O ${params.TKN_VERSION}/LICENSE"

                sh "chmod +x ${params.TKN_VERSION}/{linux,macos}/tkn"
                sh "tree ${params.TKN_VERSION}"
            }
        }
        stage('Create Tarballs') {
            steps {
                sh "tar -czvf ${params.TKN_VERSION}/tkn-linux-amd64-${params.TKN_VERSION}.tar.gz ${params.TKN_VERSION}/{LICENSE,linux/tkn} --transform='s|${params.TKN_VERSION}/||g' --transform='s|linux/||g'"
                sh "tar -czvf ${params.TKN_VERSION}/tkn-macos-amd64-${params.TKN_VERSION}.tar.gz ${params.TKN_VERSION}/{LICENSE,macos/tkn} --transform='s|${params.TKN_VERSION}/||g' --transform='s|macos/||g'"
                sh "zip -j ${params.TKN_VERSION}/tkn-windows-amd64-${params.TKN_VERSION}.zip ${params.TKN_VERSION}/{LICENSE,windows/tkn.exe}"

                sh "tar -tvf ${params.TKN_VERSION}/tkn-linux-amd64-${params.TKN_VERSION}.tar.gz"
                sh "tar -tvf ${params.TKN_VERSION}/tkn-macos-amd64-${params.TKN_VERSION}.tar.gz"
                sh "unzip -l ${params.TKN_VERSION}/tkn-windows-amd64-${params.TKN_VERSION}.zip"

                sh "rm -rf ${params.TKN_VERSION}/{linux,macos,windows,LICENSE}"
            }
        }
        stage('Calculate sha256sum') {
            steps {
                sh "cd ${params.TKN_VERSION} && sha256sum tkn-* > sha256sum.txt"
                sh "cat ${params.TKN_VERSION}/sha256sum.txt"
            }
        }
        stage('Sync to mirror') {
            steps {
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.TKN_VERSION} use-mirror-upload:/srv/pub/openshift-v4/clients/pipeline/"
                    sh "ssh use-mirror-upload ln --symbolic --force --no-dereference ${params.TKN_VERSION} /srv/pub/openshift-v4/clients/pipeline/latest"
                    sh 'ssh use-mirror-upload /usr/local/bin/push.pub.sh openshift-v4/clients/pipeline -v'
                }
            }
        }
    }
}
