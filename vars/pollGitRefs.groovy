def call(String gitUrl, String refPattern, String downstreamJob, String pollSchedule="H/5 * * * *") {
  pipeline {
    triggers { pollSCM(pollSchedule) }
    options {
      timestamps()
      buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    agent { label 'master' }
    stages {
      stage("Poll Tags") {
        agent { label 'master' }
        steps {
          script {
            def scmVars = checkout(
              scm: [$class: 'GitSCM',
                branches: [[name: refPattern]],
                userRemoteConfigs: [
                  [
                    name: 'origin',
                    url: gitUrl,
                    refspec: '+refs/heads/*:refs/remotes/origin/* +refs/tags/*:refs/remotes/origin/tags/* +refs/pull/*/head:refs/remotes/origin/pull/*/head',
                  ],
                ],
                extensions: [
                  [$class: 'CleanBeforeCheckout'],
                  [$class: 'BuildChooserSetting', buildChooser:[$class: 'AncestryBuildChooser', maximumAgeInDays: 1]],
                ],
              ],
              poll: true,
              changelog: false,
            )
            env.GIT_COMMIT = scmVars.GIT_COMMIT
            // setting build display name
            def prefix = 'origin/'
            def branch = scmVars.GIT_BRANCH.startsWith(prefix) ? scmVars.GIT_BRANCH.substring(prefix.size())
              : scmVars.GIT_BRANCH // origin/pull/1234/head -> pull/1234/head, origin/master -> master
            env.GIT_BRANCH = branch
            echo "Build on branch=${env.GIT_BRANCH}, commit=${env.GIT_COMMIT}"
            currentBuild.displayName = "${env.GIT_BRANCH}: ${env.GIT_COMMIT.substring(0, 7)}"
          }
        }
      }
      stage("Start Downstream Job") {
        steps {
          script {
            openshift.withCluster() {
              echo "Starting job ${downstreamJob}..."
              def buildSel = openshift.selector("bc", downstreamJob).startBuild(
                '-e', "GIT_BRANCH=${env.GIT_BRANCH}",
              ).narrow("build")
              timeout(time: 5) {
                buildSel.watch {
                  return !(it.object().status.phase in ["New", "Pending", "Unknown"])
                }
              }
              def build = buildSel.object()
              def buildName = build.metadata.name
              def downstreamBuildUrl = build.metadata.annotations['openshift.io/jenkins-build-uri']
              echo "Downstream build ${buildName}(${downstreamBuildUrl}) started."
            }
          }
        }
      }
    }
  }
}
