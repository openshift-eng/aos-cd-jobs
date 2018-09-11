properties(
        [
                buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
                disableConcurrentBuilds()
        ] )


b = build       job: '../aos-cd-builds/build%2Fose4.0', propagate: false

currentBuild.displayName = "${b.displayName}"

currentBuild.result = b.result
