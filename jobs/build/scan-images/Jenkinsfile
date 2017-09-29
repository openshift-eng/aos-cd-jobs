final MAIL_FROM = 'aos-cd@redhat.com'
final MAILING_LIST_CVE = ['bbarcaro@redhat.com']
final MAILING_LIST_ERR = ['bbarcaro@redhat.com']

properties([[
  $class : 'ParametersDefinitionProperty',
  parameterDefinitions: [
    [
      $class: 'BooleanParameterDefinition',
      name: 'MOCK',
      description: 'Mock run to pickup new Jenkins parameters?.',
      defaultValue: false,
    ],
    [
      $class: 'hudson.model.ChoiceParameterDefinition',
      name: 'BUILD_VERSION',
      description: 'OCP Version to build',
      defaultValue: '3.7',
      choices: ['3.7', '3.6', '3.5', '3.4', '3.3'].join('\n'),
    ],
  ],
]])

node('openshift-build-1') {
  try {
    def buildlib = null
    stage('clone') {
      dir('aos-cd-jobs') {
        checkout scm
        buildlib = load('pipeline-scripts/buildlib.groovy')
      }
      dir('oit') {
        git(
          url: 'git@github.com:openshift/enterprise-images.git',
          credentialsId: 'openshift-bot')
      }
    }
    stage('venv') {
      if(!fileExists('env')) { sh 'virtualenv env' }
      sh 'env/bin/pip install -r oit/oit/requirements.txt'
    }
    stage('update') {
      // Pull scanner image to update CVE definitions.
      sh 'sudo docker pull registry.access.redhat.com/rhel7/openscap'
    }
    stage('scan') {
      buildlib.with_virtualenv("${pwd()}/env") {
        sh """\
set -o pipefail
sudo python oit/oit/oit.py \
  --metadata-dir oit/ \
  --group 'openshift-${BUILD_VERSION}' \
  distgits:scan-for-cves \
  | tee scan.txt
"""
      }
      final ret = sh(
        returnStatus: true,
        script: 'grep -xq \'The following issues were found:\' scan.txt')
      if(ret == 0) {
        mail(
          from: MAIL_FROM, to: MAILING_LIST_CVE.join(', '),
          subject: 'jobs/build/scan-images: cve(s) found',
          body: """\
${readFile('scan.txt')}


Jenkins job: ${env.BUILD_URL}
""")
      }
    }
  } catch(err) {
    mail(
      from: MAIL_FROM, to: MAILING_LIST_ERR.join(', '),
      subject: 'jobs/build/scan-image: error',
      body: """\
Encoutered an error while running merge-and-build.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""")
    throw err
  }
}
