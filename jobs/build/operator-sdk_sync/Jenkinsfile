node {
    checkout scm
    commonlib = load('pipeline-scripts/commonlib.groovy')
    commonlib.describeJob("operator-sdk_sync", """
        <h2>Sync operator-sdk to mirror</h2>
        <b>Timing</b>: Manually, upon request. Expected to happen once every y-stream and
        sporadically on z-stream releases.
    """)
    imagePath = 'registry-proxy.engineering.redhat.com/rh-osbs/openshift-ose-operator-sdk'
}

pipeline {
    agent any

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        string(
            name: 'BUILD_TAG',
            description: "Build of ose-operator-sdk from which the contents should be extracted.<br/>" +
                         "Examples:<br/>" +
                         "<ul>" +
                         "<li>v4.7.0-202101261648.p0</li>" +
                         "<li>v4.7.0</li>" +
                         "<li>v4.7</li>" +
                         "</ul>",
            defaultValue: '',
            trim: true,
        )
        string(
            name: 'VERSION',
            description: 'Release version (name of directories published in the mirror)',
            defaultValue: '',
            trim: true,
        )
    }

    stages {
        stage('pre-flight') {
            steps {
                script {
                    if (!params.BUILD_TAG) {
                        error 'BUILD_TAG must be specified'
                    }
                    if (!params.VERSION) {
                        error 'VERSION must be specified'
                    }
                    currentBuild.displayName = "${params.VERSION}"
                    currentBuild.description = "${params.BUILD_TAG}"
                }
            }
        }
        stage('extract binaries') {
            steps {
                script {
                    def manifestList = readJSON(
                        text: sh(
                            script: "skopeo inspect --raw docker://${imagePath}:${params.BUILD_TAG}",
                            returnStdout: true,
                        )
                    ).manifests
                    manifestList.each {
                        sh "rm -rf ./${params.VERSION} && mkdir ./${params.VERSION}"

                        dir("./${params.VERSION}") {
                            sh "oc image extract ${imagePath}@${it.digest} --path /usr/local/bin/operator-sdk:. --confirm"
                            sh "chmod +x operator-sdk"
                        }

                        def arch = it.platform.architecture == 'amd64' ? 'x86_64' : it.platform.architecture
                        sshagent(['aos-cd-test']) {
                            sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/${arch}/clients/operator-sdk/"
                            sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/${arch}/clients/operator-sdk/latest"
                            sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/${arch}/clients/operator-sdk -v"
                        }
                    }
                }
            }
        }
    }
}
