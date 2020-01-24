#!/usr/bin/env groovy

pipeline {
    agent any

    parameters {
        string(
            name: "RPM_URL",
            description: "Redistributable RPM URL. Example: http://brew-task-repos.usersys.redhat.com/repos/official/openshift-odo/1.0.3/1.el7/x86_64/openshift-odo-redistributable-1.0.3-1.el7.x86_64.rpm",
            defaultValue: ""
        )
        string(
            name: "VERSION",
            description: "Desired version name. Example: v1.0.3",
            defaultValue: ""
        )
    }

    stages {
        stage("Download RPM") {
            steps {
                sh "wget ${params.RPM_URL} -O odo.rpm"
            }
        }
        stage("Extract RPM contents") {
            steps {
                sh "rpm2cpio odo.rpm | cpio -id"
                sh "rm -rf ${VERSION} && mkdir ${VERSION}"
                sh "mv ./usr/share/openshift-odo-redistributable/* ${VERSION}/"
                sh "tree ${VERSION}"
            }
        }
        stage("Sync to mirror") {
            steps {
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/odo/"
                    sh "ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com ln -sfn ${VERSION} /srv/pub/openshift-v4/clients/odo/latest"
                    sh "ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.pub.sh openshift-v4/clients/odo -v"
                }
            }
        }
    }
}
