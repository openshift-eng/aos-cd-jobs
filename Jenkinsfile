// Update-branches job

properties(
  [
    disableConcurrentBuilds(),
    disableResume(),
    buildDiscarder(
      logRotator(
        artifactDaysToKeepStr: '60',
        daysToKeepStr: '60')
    ),
  ]
)

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
  if(env.WORKSPACE == null) {
    env.WORKSPACE = WORKSPACE = pwd()
  }
}

node('openshift-build-1') {
  try {
    timeout(time: 30, unit: 'MINUTES') {
      deleteDir()
      set_workspace()
      dir('aos-cd-jobs') {
        stage('clone') {
          checkout scm
          sh 'git checkout master'
        }
        stage('run') {
          final url = sh(
            returnStdout: true,
            script: 'git config remote.origin.url')
          if(!(url =~ /^[-\w]+@[-\w]+(\.[-\w]+)*:/)) {
            error('This job uses ssh keys for auth, please use an ssh url')
          }
          def prune = true, key = 'openshift-bot'
          if(url.trim() != 'git@github.com:openshift-eng/aos-cd-jobs.git') {
            prune = false
            key = "${(url =~ /.*:([^\/]+)/)[0][1]}-aos-cd-bot"
          }
          sshagent([key]) {
            sh """\
python3 -m venv ../env/
. ../env/bin/activate
pip install gitpython
export GIT_PYTHON_TRACE=full
${prune ? 'python -m aos_cd_jobs.pruner' : 'echo Fork, skipping pruner'}
python -m aos_cd_jobs.updater
"""
          }
        }
      }
    }
  } catch(err) {
    mail(
      to: 'jupierce@redhat.com',
      from: "aos-cicd@redhat.com",
      subject: 'aos-cd-jobs-branches job: error',
      body: """\
Encountered an error while running the aos-cd-jobs-branches job: ${err}\n\n
Jenkins job: ${env.BUILD_URL}
""")
    throw err
  }
}
