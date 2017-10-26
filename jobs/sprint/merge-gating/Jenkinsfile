#!/usr/bin/env groovy

properties(
        [
            buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
            [$class : 'ParametersDefinitionProperty',
              parameterDefinitions:
                  [
                          [     
                                  name: 'CI_SERVER',
                                  $class: 'hudson.model.StringParameterDefinition', 
                                  defaultValue: 'https://api.ci.openshift.org:443', 
                                  description: 'OpenShift CI Server', 
                          ],
                          [
                                  name: 'MAIL_LIST_FAILURE',
                                  $class: 'hudson.model.StringParameterDefinition',
                                  defaultValue: 'jupierce@redhat.com',
                                  description: 'Failure Mailing List'
                          ],
                          [
                                  name: 'MERGE_GATE_LABELS',
                                  $class: 'hudson.model.ChoiceParameterDefinition',
                                  choices: ['none', 'kind/bug'].join('\n'),
                                  defaultValue: 'none',
                                  description: 'Select what label is required to merge PRs'
                          ],
                          [
                                  name: 'TEST_ONLY',
                                  $class: 'hudson.model.BooleanParameterDefinition',
                                  defaultValue: false,
                                  description: 'Do not push results?',
                          ],
                          [
                                  name: 'MOCK',
                                  $class: 'hudson.model.BooleanParameterDefinition',
                                  defaultValue: false,
                                  description: 'Mock run to pickup new Jenkins parameters?',
                          ],
                          [
                                  name: 'TARGET_NODE',
                                  description: 'Jenkins agent node',
                                  $class: 'hudson.model.StringParameterDefinition',
                                  defaultValue: 'openshift-build-1'
                          ],
                  ]
            ],
            disableConcurrentBuilds()
        ]
)

TEST_ONLY = TEST_ONLY.toBoolean()

if ( MERGE_GATE_LABELS == "none" ) {
    MERGE_GATE_LABELS = ""
}

def set_required_labels(template_filename, label) {
    sq = readFile(template_filename)
    sq = sq.replaceAll('additional-required-labels: ".*"', "additional-required-labels: \"${label}\"")
    writeFile file:template_filename, text:sq
}

node(TARGET_NODE) {

    checkout scm

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    try {

        sshagent(["openshift-bot"]) {

            if ( MERGE_GATE_LABELS != null ) {
                    // Clone release tools to manage merge gate label
                    sh "rm -rf release"
                    sh "git clone git@github.com:openshift/release.git"
                    dir ("release/cluster/ci/config/submit-queue") {
                        final files = findFiles(glob: 'submit_queue*.yaml')
                        for(int i = 0; i < files.size(); ++i) {
                            set_required_labels(files[i].name, MERGE_GATE_LABELS)
                        }

                        sh "git add -u"
                        sh "git commit --allow-empty -m 'Setting required-labels to: ${MERGE_GATE_LABELS}'"

                        if ( ! TEST_ONLY ) {
                            sh "git push"
                        } else {
                            echo "SKIPPING PUSH SINCE THIS IS A TEST RUN"
                        }

                        EXTRA_ARGS=""
                        if ( TEST_ONLY ) {
                            echo "RUNNING APPLY IN DRY-RUN SINCE THIS IS A TEST RUN"
                            EXTRA_ARGS="--dry-run"
                        }

                        withCredentials([string(credentialsId: 'aos-cd-sprint-control-token', variable: 'TOKEN')]) {
                            for(int i = 0; i < files.size(); ++i) {
                                sh "oc-3.7 process -f ${files[i].name} | oc-3.7 -n ci --server=${CI_SERVER} --token=$TOKEN apply ${EXTRA_ARGS} -f -"
                            }
                        }
                    }
            }

        }

    } catch ( err ) {
        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error running sprint control",
                body: """${err}

    Jenkins job: ${env.BUILD_URL}
    """);
        throw err
    }


}
