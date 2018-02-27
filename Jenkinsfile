properties( 
        [
                buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
                disableConcurrentBuilds()
        ] )


b = build       job: '../aos-cd-builds/build%2Focp', propagate: false,
                parameters: [   [$class: 'StringParameterValue', name: 'BUILD_VERSION', value: '3.9'],
                                [$class: 'StringParameterValue', name: 'BUILD_MODE', value: 'pre-release'],
                                ]

currentBuild.displayName = "ocp:${b.displayName}"
currentBuild.result = b.result
