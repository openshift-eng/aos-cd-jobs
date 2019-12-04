#!/usr/bin/env groovy

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// RPMS can periodically be synced with https://unix.stackexchange.com/a/189

backupPlan = [
    srcHost: 'buildvm.openshift.eng.bos.redhat.com',
    destHost: 'buildvm2.openshift.eng.bos.redhat.com',
    backupPath: '/mnt/workspace/backups/buildvm', // must exist on both src and dest host
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
        '/usr/lib/jenkins',

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
        echo "This (${env.BUILD_URL}) is not the backupPlan.srcHost (${backupPlan.srcHost}); skipping"
        return
    }

    // 52 backups a year; then backups are overwritten
    def weekOfYear = new Date().format("w")
    tarballPath = "${backupPlan.backupPath}/${backupPlan.srcHost}.week-${weekOfYear}.tgz"
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

    tarRes = commonlib.shell(
            returnAll: true,
            script: cmds.join('\n')
    )

    if (tarRes.returnStatus != 0) {
        error("Error creating local tar")
    }

    scpRes = commonlib.shell(
            returnAll: true,
            script: """
              ssh -l root ${backupPlan.destHost} mkdir -p ${backupPlan.backupPath}
              scp ${tarballPath} root@${backupPlan.destHost}:${tarballPath}
            """
    )

    if (scpRes.returnStatus != 0) {
        error("Error copying tar to destination host: ${backupPlan.destHost}")
    }

}

return this
