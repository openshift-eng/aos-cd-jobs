
properties( [
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
    disableConcurrentBuilds(),
    pipelineTriggers([[$class: 'TimerTrigger', spec: '0 2 * * 1,3,5']])] )

description = ""
failed = false

b = build job: '../aos-cd-builds/build%2Fose3.6', propagate: false
description += "${b.displayName} - ${b.result}\n"
failed |= (b.result != "SUCCESS")

currentBuild.description = description.trim()
currentBuild.result = failed?"FAILURE":"SUCCESS"
