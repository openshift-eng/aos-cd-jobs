properties(
        [
                buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
                disableConcurrentBuilds()
        ] )


b = build       job: '../aos-cd-builds/build%2Focp4', propagate: false,
                parameters: [   [$class: 'StringParameterValue', name: 'BUILD_VERSION', value: '4.1'],
                                [$class: 'StringParameterValue', name: 'BUILD_MODE', value: 'online:int'],
                                ]

currentBuild.displayName = "ocp:${b.displayName}"
currentBuild.result = b.result
