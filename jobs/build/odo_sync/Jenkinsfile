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
        stage("Validate params") {
            if (!params.RPM_URL) {
                error "RPM_URL must be specified"
            }
            if (!params.VERSION) {
                error "VERSION must be specified"
            }
        }
        stage("Download RPM") {
            steps {
                sh "rm --force odo.rpm"
                sh "wget --no-verbose ${params.RPM_URL} --output-document=odo.rpm"
            }
        }
        stage("Extract RPM contents") {
            steps {
                sh "rpm2cpio odo.rpm | cpio --extract --make-directories"
                sh "rm --recursive --force ${params.VERSION} && mkdir ${params.VERSION}"
                sh "mv --verbose ./usr/share/openshift-odo-redistributable/* ${params.VERSION}/"
                sh "tree ${params.VERSION}"
            }
        }
        stage("Sync to mirror") {
            steps {
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/odo/"
                    sh "ssh ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/clients/odo/latest"
                    sh "ssh /usr/local/bin/push.pub.sh openshift-v4/clients/odo -v"
                }
            }
        }
    }
}
