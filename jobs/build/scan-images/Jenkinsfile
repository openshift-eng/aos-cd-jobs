final MAIL_FROM = 'aos-cd@redhat.com'
final MAILING_LIST_CVE = ['bbarcaro@redhat.com']
final MAILING_LIST_ERR = ['bbarcaro@redhat.com']

properties([[
  $class : 'ParametersDefinitionProperty',
  parameterDefinitions: [
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
    stage('clone') { dir('aos-cd-jobs') { checkout scm } }
    stage('update') {
      // Pull scanner image to update CVE definitions.
      sh 'sudo docker pull registry.access.redhat.com/rhel7/openscap'
    }
    stage('scan') {
      sh """\
aos-cd-jobs/build-scripts/ose_images/ose_images.sh scan_images \
  --user ocp-build \
  --branch 'rhaos-${BUILD_VERSION}-rhel-7' \
  --group base
cat scan.txt
"""
      final ret = sh(
        returnStatus: true,
        script: 'grep -xq \'The following issues were found:\' scan.txt')
      if(ret == 0) {
        mail(
          from: MAIL_FROM, to: MAILING_LIST_CVE.join(', '),
          subject: 'jobs/build/scan-images: cve(s) found',
          body: readFile('scan.txt'))
      }
    }
  } catch(err) {
    mail(
      from: MAIL_FROM, to: MAILING_LIST_ERR.join(', '),
      subject: 'jobs/build/scan-image: error',
      body: "${err}")
    throw err
  }
}
