properties(
  [
    disableConcurrentBuilds()
  ]
)

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
  if(env.WORKSPACE == null) {
    env.WORKSPACE = pwd()
  }
}

node('buildvm-devops') {
  try {
    deleteDir()
    set_workspace()
    stage('clone') {
      dir('aos-cd-jobs') {
        checkout scm
        sh 'git checkout master'
      }
    }
    stage('run') {
      sshagent(['openshift-bot']) { // git repo privileges stored in Jenkins credential store
        sh '''\
virtualenv env/
. env/bin/activate
pip install gitpython
export PYTHONPATH=$PWD/aos-cd-jobs
python aos-cd-jobs/aos_cd_jobs/pruner.py
python aos-cd-jobs/aos_cd_jobs/updater.py
'''
      }
    }
  } catch(err) {
    mail(
      to: 'bbarcaro@redhat.com',
      subject: 'aos-cd-jobs-branches job: error',
      body: """\
Encoutered an error while running the aos-cd-jobs-branches job: ${err}\n\n
Jenkins job: ${env.BUILD_URL}
""")
    throw err
  }
}
