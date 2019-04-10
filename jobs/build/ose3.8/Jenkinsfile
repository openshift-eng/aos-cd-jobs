properties( 
        [
                buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
                disableConcurrentBuilds()
        ] )


b = build       job: 'build%2Focp3', propagate: false,
                parameters: [   [$class: 'StringParameterValue', name: 'BUILD_VERSION', value: '3.8'],
                                [$class: 'StringParameterValue', name: 'BUILD_MODE', value: 'release'],
                                ]

currentBuild.displayName = "ocp:${b.displayName}"
currentBuild.result = b.result
