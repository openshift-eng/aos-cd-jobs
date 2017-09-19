#!/usr/bin/env groovy

def mail_success(list,detail,warn) {
    body = "Cluster ${CLUSTER_NAME} upgrade details:\n"
    if ( warn ) {
        body += "\nWARNING: post-upgrade smoke test was not successful: ${warn}\n"
    }
    body += "\n${detail}\n\nJenkins job: ${env.BUILD_URL}\n"
    mail(
        to: "${list}",
        from: "aos-cd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "[aos-cicd] Cluster upgrade complete: ${CLUSTER_NAME}",
        body: body
    );
}

@Library('aos_cd_ops') _

// Ask the shared library which clusters this job should act on
cluster_choice = aos_cd_ops_data.getClusterList("${env.BRANCH_NAME}").join("\n")  // Jenkins expects choice parameter to be linefeed delimited

properties(
        [[$class              : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-cicd@redhat.com, aos-qe@redhat.com, devtools-saas@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com, mwoodson@redhat.com', description: 'Success for minor cluster operation', name: 'MAIL_LIST_SUCCESS_MINOR'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com, mwoodson@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The specification of the cluster to affect'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to prevent input prompt. Select quiet to prevent aos-cicd emails. Select silent to prevent any success email.'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OpenShift version (e.g. 3.6.173.0.37-1.git.0.fd828e7.el7)', name: 'OPENSHIFT_VERSION'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Docker version (e.g. 1.12.6-48.git0fdc778.el7)', name: 'DOCKER_VERSION'],
                          [$class: 'hudson.model.TextParameterDefinition', defaultValue: '', description: 'Additional options (key=value linefeed delimited)', name: 'ADDITIONAL_OPTS'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                  ]
         ]]
)

node('openshift-build-1') {

    checkout scm

    def deploylib = load( "pipeline-scripts/deploylib.groovy")
    deploylib.initialize(CLUSTER_SPEC, ADDITIONAL_OPTS)

    currentBuild.displayName = "#${currentBuild.number} - ${CLUSTER_NAME}"

    try {

        // ssh key is named after the environment it can impact
        sshagent([CLUSTER_ENV]) {

            stage( "pre-check" ) {
                deploylib.run("pre-check", [ "cicd_docker_version" : DOCKER_VERSION.trim(), "cicd_openshift_version" : OPENSHIFT_VERSION.trim() ])
            }

            if ( MODE != "automatic" ) {
                input "Are you certain you want to =====>UPGRADE<===== the =====>${CLUSTER_NAME}<===== cluster?"
            }

            stage( "pre-upgrade status" ) {
                echo "Cluster status BEFORE upgrade:"
                deploylib.run("status")
            }

            stage( "enable maintenance" ) {
                // deploylib.run( "enable-statuspage" )
                deploylib.run( "enable-zabbix-maint" )
                deploylib.run( "disable-config-loop" )
            }

            stage( "upgrade" ) {
                deploylib.run( "upgrade-control-plane", [ "cicd_docker_version" : DOCKER_VERSION.trim(), "cicd_openshift_version" : OPENSHIFT_VERSION.trim() ] )
                deploylib.run( "upgrade-nodes", [ "cicd_docker_version" : DOCKER_VERSION.trim(), "cicd_openshift_version" : OPENSHIFT_VERSION.trim() ] )
                deploylib.run( "upgrade-logging" )
                deploylib.run( "upgrade-metrics" )
            }

            stage( "config-loop" ) {
                deploylib.run( "commit-config-loop" )
                deploylib.run( "enable-config-loop" )
                deploylib.run( "run-config-loop" )
            }

            stage( "disable maintenance" ) {
                deploylib.run( "disable-zabbix-maint" )
                //deploylib.run( "disable-statuspage" )
            }

            stage( "post-upgrade status" ) {
                POST_STATUS = deploylib.run("status", null, true)
                echo "Cluster status AFTER upgrade:"
                echo POST_STATUS
            }

            stage( "smoketest" ) {
                warn = null
                if ( "${env.BRANCH_NAME}".contains( "starter" ) ) {
                    smoketest = build job: 'starter%2Fsmoke-test', propagate: false,
                                      parameters: [
                                          [$class: 'StringParameterValue', name: 'CLUSTER_SPEC', value: CLUSTER_SPEC],
                                          [$class: 'BooleanParameterValue', name: 'MAIL_RESULTS', value: false],
                                      ]

                    POST_STATUS += "\nSmoke test results: ${smoketest.result}\n"

                    if ( smoketest.resultIsWorseOrEqualTo( "UNSTABLE" ) ) {
                        warn = smoketest.absoluteUrl
                    }
                }
            }

            minorUpdate = [ 'test-key', 'cicd' ].contains( CLUSTER_NAME ) || MODE == "quiet"

            if ( MODE != "silent" ) {
                // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
                mail_success(minorUpdate?MAIL_LIST_SUCCESS_MINOR:MAIL_LIST_SUCCESS, POST_STATUS, warn)
                // just testing
            }

            stage ( "performance check" ) {
                /* // Disabled until SVT works out issues in their test.
                if ( ( CLUSTER_NAME == "free-int" || CLUSTER_NAME =="test-key" ) && ( OPERATION == "install" || OPERATION == "reinstall" || OPERATION == "upgrade" )  ) {
                    // Run perf1 test on free-int
                    build job: 'starter%2Fperf',
                        propagate: false,
                        parameters: [
                            [$class: 'hudson.model.StringParameterValue', name: 'CLUSTER_NAME', value: CLUSTER_NAME],
                            [$class: 'hudson.model.StringParameterValue', name: 'OPERATION', value: 'perf1'],
                            [$class: 'hudson.model.StringParameterValue', name: 'MODE', value: 'automatic'],
                        ]
                }
                */
            }

        }

    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error during upgrade on cluster ${CLUSTER_NAME}",
                body: """Encountered an error: ${err}

Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }


    if ( MODE != "silent" ) {
        deploylib.send_ci_msg_for_cluster( CLUSTER_NAME )
    }

}
