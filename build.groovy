#!/usr/bin/env groovy

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// RPMS can periodically be synced with https://unix.stackexchange.com/a/189

backupPlan = [
    srcHost: 'buildvm.hosts.prod.psi.bos.redhat.com',
    backupPath: '/mnt/jenkins-workspace/backups/buildvm', // must exist on both src and dest host
    files: [
        '/etc/sysconfig/jenkins',  // config file for jenkins server
        '/etc/sysconfig/docker', // insecure registries
        '/etc', // for reference

        // keys for accessing mirror repositories
        '/var/lib/yum/client-cert.pem',
        '/var/lib/yum/client-key.pem',

        // /home/jenkins resolves to nfs share, so nothing needs to be copied

        '/home/jenkins/.ssh',
        '/home/jenkins/.config',
        '/home/jenkins/.ssh',
        '/home/jenkins/bin',
        '/home/jenkins/.gem',
        '/home/jenkins/.aws',
        '/home/jenkins/.docker',
        '/home/jenkins/.kube',
        '/home/jenkins/credentials',
        '/home/jenkins/kubeconfigs',
        '/home/jenkins/go',

        // Jenkins war
        '/usr/share/java',

        // Jenkins configuration, plugins, etc
        '/mnt/nfs/jenkins_home/*.xml',
        '/mnt/nfs/jenkins_home/plugins',
        '/mnt/nfs/jenkins_home/users',
        '/mnt/nfs/jenkins_home/userContent',
        '/mnt/nfs/jenkins_home/fingerprints',
        '/mnt/nfs/jenkins_home/secrets',
        '/mnt/nfs/jenkins_home/nodes',
        '/mnt/nfs/jenkins_home/fingerprints',
        '/mnt/nfs/jenkins_home/updates',
        '/mnt/nfs/jenkins_home/update-center-rootCAs',
        '/mnt/nfs/jenkins_home/jobs/*/jobs/*/config.xml',
        '/mnt/nfs/jenkins_home/jobs/*/config.xml',

        // firewall rules
        '/root/network',
    ],
]

@NonCPS
def buildTarCommand(tarballPath) {
    // sudo required to read some files owned by root
    def cmd = "sudo tar zcvf ${tarballPath}"
    for ( file in backupPlan.files ) {
        cmd += " ${file}"
    }
    return cmd.trim()
}

def stageRunBackup() {

    if (env.BUILD_URL.indexOf(backupPlan.srcHost) == -1) {
        error("This (${env.BUILD_URL}) is not the backupPlan.srcHost (${backupPlan.srcHost}); skipping")
    }

    // 52 backups a year; then backups are overwritten
    def weekOfYear = new Date().format("w")
    tarballName = "${backupPlan.srcHost}.week-${weekOfYear}.tgz"
    tarballPath = "${backupPlan.backupPath}/${tarballName}"
    def tarCmd = buildTarCommand(tarballPath)

    def cmds = [
        "mkdir -p d${backupPlan.backupPath}",
        "sudo rm -f ${tarballPath}",
        "${tarCmd}"
    ]

    if ( params.DRY_RUN ) {
        def dry_run_cmds = '> ' + cmds.join('\n> ')
        echo "Would have run:\n${dry_run_cmds}"
        return
    }

    // Create tar archives
    tarRes = commonlib.shell(
            returnAll: true,
            script: cmds.join('\n')
    )

    // Even if an error raised during archive creation,
    // upload to S3 what we have... better than nothing
    withCredentials([aws(credentialsId: 's3-art-buildvm-backup', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
        commonlib.shell("aws s3 cp ${tarballPath} s3://art-buildvm-backup/archives/${tarballName}")
    }

    // Notify errors raised during tarball creation
    if (tarRes.returnStatus != 0) {
        error("Error creating local tar")
    }
}

return this
