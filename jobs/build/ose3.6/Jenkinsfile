
error( "3.6 build intentionally disabled for now" )

properties( 
        [
                [$class: 'BuildDiscarderProperty', strategy: [$class: 'LogRotator', artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '60']],
                disableConcurrentBuilds()
        ] )


b = build       job: '../aos-cd-builds/build%2Fose', propagate: false,
                parameters: [   [$class: 'StringParameterValue', name: 'OSE_MAJOR', value: '3'],
                                [$class: 'StringParameterValue', name: 'OSE_MINOR', value: '6'],
                                [$class: 'StringParameterValue', name: 'BUILD_MODE', value: 'enterprise:pre-release'],
                                ]

currentBuild.displayName = "ose:${b.displayName}"
currentBuild.result = b.result
