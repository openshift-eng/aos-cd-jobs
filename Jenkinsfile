properties(
  [
    disableConcurrentBuilds()
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
          sshagent(['openshift-bot']) {
            sh '''\
virtualenv ../env/
. ../env/bin/activate
pip install gitpython
python -m aos_cd_jobs.pruner
python -m aos_cd_jobs.updater
'''
          }
        }
      }
    }
  } catch(err) {
    mail(
      to: 'bbarcaro@redhat.com, jupierce@redhat.com',
      from: "aos-cd@redhat.com",
      subject: 'aos-cd-jobs-branches job: error',
      body: """\
Encoutered an error while running the aos-cd-jobs-branches job: ${err}\n\n
Jenkins job: ${env.BUILD_URL}
""")
    throw err
  }
}
