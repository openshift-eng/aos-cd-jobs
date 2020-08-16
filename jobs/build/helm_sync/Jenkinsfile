#!/usr/bin/env groovy
node {
    load('pipeline-scripts/commonlib.groovy').describeJob("helm_sync", """
        ---------------------------------------
        Sync contents of the helm RPM to mirror
        ---------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/helm/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "RPM_URL",
            description: "Redistributable RPM URL. Example: http://download.eng.bos.redhat.com/brewroot/vol/rhel-7/packages/helm/3.0.1/4.el7/x86_64/helm-redistributable-3.0.1-4.el7.x86_64.rpm",
            defaultValue: ""
        )
        string(
            name: "VERSION",
            description: "Desired version name. Example: v3.0.1",
            defaultValue: ""
        )
    }

    stages {
        stage("Validate params") {
            steps {
                script {
                    if (!params.RPM_URL) {
                        error "RPM_URL must be specified"
                    }
                    if (!params.VERSION) {
                        error "VERSION must be specified"
                    }
                }
            }
        }
        stage("Download RPM") {
            steps {
                sh "rm --force helm-redistributable.rpm"
                sh "wget --no-verbose ${params.RPM_URL} --output-document=helm-redistributable.rpm"
            }
        }
        stage("Extract RPM contents") {
            steps {
                sh "rpm2cpio helm-redistributable.rpm | cpio --extract --make-directories"
                sh "rm --recursive --force ${params.VERSION} && mkdir ${params.VERSION}"
                sh "mv --verbose ./usr/share/helm-redistributable/* ${params.VERSION}/"
                sh "mv --verbose ${params.VERSION}/*/* ${params.VERSION}/ && /bin/ls --directory ${params.VERSION}/*/ | xargs rmdir"
                sh "tree ${params.VERSION}"
            }
        }
        stage("Sync to mirror") {
            steps {
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/helm/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/clients/helm/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.pub.sh openshift-v4/clients/helm -v"
                }
            }
        }
    }
}
