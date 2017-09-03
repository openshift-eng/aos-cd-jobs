
properties( [
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
    disableConcurrentBuilds(),
    pipelineTriggers([[$class: 'TimerTrigger', spec: '0 1 * * *']])] )

description = ""
failed = false

// Needs to change to be ocp
/*
b = build job: '../aos-cd-builds/build%2Fose3.6', propagate: false
failed |= (b.result != "SUCCESS")
description += "${b.displayName} - ${b.result}\n"
currentBuild.description = description.trim()

currentBuild.result = failed?"FAILURE":"SUCCESS"
*/