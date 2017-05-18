
properties( [
    [$class: 'BuildDiscarderProperty', strategy: [$class: 'LogRotator', artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '60']],
    disableConcurrentBuilds(),
    [$class: 'HudsonNotificationProperty', enabled: false],
    [$class: 'RebuildSettings', autoRebuild: false, rebuildDisabled: false],
    [$class: 'ThrottleJobProperty', categories: [], limitOneJobWithMatchingParams: false, maxConcurrentPerNode: 0, maxConcurrentTotal: 0, paramsToUseForLimit: '', throttleEnabled: false, throttleOption: 'project'],
    pipelineTriggers([[$class: 'TimerTrigger', spec: '30 18 * * 2,4']])] )

description = ""
failed = false


b = build job: '../aos-cd-builds/build%2Fose3.5', propagate: false
description += "${b.displayName} - ${b.result}\n"
failed |= (b.result != "SUCCESS")

b = build job: '../aos-cd-builds/build%2Fose3.4', propagate: false
description += "${b.displayName} - ${b.result}\n"
failed |= (b.result != "SUCCESS")

b = build job: '../aos-cd-builds/build%2Fose3.3', propagate: false
description += "${b.displayName} - ${b.result}\n"
failed |= (b.result != "SUCCESS")


currentBuild.description = description.trim()
currentBuild.result = failed?"FAILURE":"SUCCESS"
