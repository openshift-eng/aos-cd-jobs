#!/usr/bin/env groovy

def mail_success(list,detail,warn) {
    body = "Cluster ${CLUSTER_NAME} upgrade details:\n"
    if ( warn ) {
        body += "\nWARNING: post-upgrade smoke test was not successful:\n${warn}\n"
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
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The specification of the cluster to affect'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to skip confirmation prompt. Select quiet to prevent aos-cicd emails. Select silent to prevent any success email.'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],

                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-control-plane?', name: 'UPGRADE_CONTROL_PLANE'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Run upgrade-jenkins-image-stream?', name: 'UPGRADE_JENKINS_IMAGE_STREAM'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-nodes?', name: 'UPGRADE_NODES'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-logging?', name: 'UPGRADE_LOGGING'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-metrics?', name: 'UPGRADE_METRICS'],

                  ]
         ]]
)

node('openshift-build-1') {

    checkout scm
    
    def commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    MAIL_LIST_SUCCESS_MINOR = "jupierce@redhat.com, mwoodson@redhat.com"
    
    // Get default values from aos-cd-jobs-secrets
    MAIL_LIST_SUCCESS = MAIL_LIST_SUCCESS_DEFAULT = aos_cd_ops_data.getMailingList("on_success", CLUSTER_SPEC)
    MAIL_LIST_FAILURE = MAIL_LIST_FAILURE_DEFAULT = aos_cd_ops_data.getMailingList("on_failure", CLUSTER_SPEC)
    ADDITIONAL_OPTS = ADDITIONAL_OPTS_DEFAULT = aos_cd_ops_data.getOptionsList(CLUSTER_SPEC)

    if ( MODE != "automatic" ) {
        parms = input(
                message: 'Review/update the parameters for this before proceeding.',
                parameters: [
                        choice(choices: MAIL_LIST_SUCCESS_DEFAULT.join("\n"), description: 'Who to email if the upgrade succeeds. ', name: 'MAIL_LIST_SUCCESS'),
                        choice(choices: MAIL_LIST_FAILURE_DEFAULT.join("\n"), description: 'Who to email if the upgrade encounters an error. ', name: 'MAIL_LIST_FAILURE'),
                        text(defaultValue: ADDITIONAL_OPTS_DEFAULT, description: 'Additional options to pass to CD operations. ', name: 'ADDITIONAL_OPTS')
                ]
        )

        // Store any changes that the user made
        MAIL_LIST_SUCCESS = parms.MAIL_LIST_SUCCESS
        MAIL_LIST_FAILURE = parms.MAIL_LIST_FAILURE
        ADDITIONAL_OPTS = parms.ADDITIONAL_OPTS
    }

    def deploylib = load( "pipeline-scripts/deploylib.groovy")
    deploylib.initialize(CLUSTER_SPEC, ADDITIONAL_OPTS)

    currentBuild.displayName = "#${currentBuild.number} - ${CLUSTER_NAME}"

    try {

        // ssh key is named after the environment it can impact
        sshagent([CLUSTER_ENV]) {

            stage( "pre-check" ) {
                deploylib.run("pre-check")
            }

            if ( MODE != "automatic" ) {
                input "Are you certain you want to =====>UPGRADE<===== the =====>${CLUSTER_NAME}<===== cluster?"
            }

            stage( "pre-upgrade status" ) {
                echo "Cluster status BEFORE upgrade:"
                deploylib.run("status")
            }

            stage( "enable maintenance" ) {
                deploylib.run( "enable-statuspage" )
                deploylib.run( "enable-zabbix-maint" )
                deploylib.run( "disable-config-loop" )
            }

            stage( "upgrade: control plane" ) {
                if (UPGRADE_CONTROL_PLANE.toBoolean()) {
                    deploylib.run("upgrade-control-plane")
                }
            }

            stage( "upgrade: nodes" ) {
                if (UPGRADE_JENKINS_IMAGE_STREAM.toBoolean()) {
                    deploylib.run("update-jenkins-imagestream")
                }

                if (UPGRADE_NODES.toBoolean()) {
                    deploylib.run("upgrade-nodes")
                }
            }

            stage ("upgrade: logging") {
                if (UPGRADE_LOGGING.toBoolean()) {
                    deploylib.run("upgrade-logging")
                }
            }

            stage ("upgrade: metrics" ) {
                if ( UPGRADE_METRICS.toBoolean()  ) {
                    deploylib.run( "upgrade-metrics" )
                }
            }

            stage ( "upgrade: misc" ) {
                if ( UPGRADE_NODES.toBoolean()  ) {
                    deploylib.run( "unschedule-extra-nodes" ) // Used to scale down dedicated instance if extra node is created prior to upgrade to ensure capacity.
                }
            }

            stage( "config-loop" ) {
                deploylib.run( "commit-config-loop" )
                deploylib.run( "enable-config-loop" )
                deploylib.run( "run-config-loop" )
            }

            stage( "disable maintenance" ) {
                deploylib.run( "disable-zabbix-maint" )
                deploylib.run( "disable-statuspage" )
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


    if ( MODE != "silent" && "${env.BRANCH_NAME}".contains( "starter" )  ) {       
        try {
            // Send out a CI message for QE
            build job: 'starter%2Fsend-ci-msg',
                    propagate: false,
                    parameters: [
                            [$class: 'hudson.model.StringParameterValue', name: 'CLUSTER_SPEC', value: CLUSTER_SPEC],
                    ]
        } catch ( err2 ) {
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error sending CI msg for cluster ${CLUSTER_NAME}",
                    body: """Encountered an error: ${err2}

        Jenkins job: ${env.BUILD_URL}
        """);

        }
    }

}
