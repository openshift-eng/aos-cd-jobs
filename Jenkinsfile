properties(
  [
    disableConcurrentBuilds()
  ]
)

node('buildvm-devops') {
  sshagent(['openshift-bot']) { // git repo privileges stored in Jenkins credential store
    echo "Bruno's branch split pipeline"
  }
}
