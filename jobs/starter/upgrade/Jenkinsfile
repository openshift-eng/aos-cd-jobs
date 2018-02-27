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

// Allows a user to override aos-cd-jobs-secrets with common repos.
repo_setup_opts = [ "Default for cluster",
    "online-int (non-ga build)",
    "online-stg (non-ga build)",
    "online-prod (non-ga build)",
    "3.7 (latest non-ga build)",
    "3.8 (latest non-ga build)",
    "3.9 (latest non-ga build)",
    "3.10 (latest non-ga build)",
    "3.11 (latest non-ga build)",
    "3.12 (latest non-ga build)",
]

properties(
        [[$class              : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The specification of the cluster to affect'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to skip confirmation prompt. Select quiet to prevent aos-cicd emails. Select silent to prevent any success email.'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: repo_setup_opts.join("\n"), name: 'REPO_SETUP', description: 'Initializes the repo options for the job. User will be prompted to adjust/override before the job runs.'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],


                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run storage-migration?', name: 'RUN_STORAGE_MIGRATION'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-control-plane?', name: 'UPGRADE_CONTROL_PLANE'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Run upgrade-jenkins-image-stream?', name: 'UPGRADE_JENKINS_IMAGE_STREAM'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-nodes?', name: 'UPGRADE_NODES'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-logging?', name: 'UPGRADE_LOGGING'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run upgrade-metrics?', name: 'UPGRADE_METRICS'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: true, description: 'Run online-deployer?', name: 'UPGRADE_ONLINE_COMPONENTS'],

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

    ADDITIONAL_OPTS_PREFS=[:]
    if ( REPO_SETUP != repo_setup_opts[0] ) {
        repo = REPO_SETUP.split(" ")[0]   // Anything after the first space is informational
        if ( repo.contains(".") ) { // If the version if "3.X", go ahead and set the openshift version
            ADDITIONAL_OPTS_PREFS["cicd_openshift_version"] = repo
            repo = "enterprise-${repo}"  // the actual directory for the non "online-X" repos
        } else {
            ADDITIONAL_OPTS_PREFS["cicd_openshift_version"] = ""
        }
        ADDITIONAL_OPTS_PREFS["cicd_yum_main_url"] = "https://mirror.openshift.com/enterprise/${repo}/latest/x86_64/os"
        ADDITIONAL_OPTS_PREFS["cicd_yum_openshift_ansible_url"] = "https://mirror.openshift.com/enterprise/${repo}/latest/x86_64/os/Packages"
    }

    ADDITIONAL_OPTS = ADDITIONAL_OPTS_DEFAULT = aos_cd_ops_data.getOptionsList(CLUSTER_SPEC, ADDITIONAL_OPTS_PREFS)


    if ( MODE != "automatic" ) {
        parms = input(
                message: 'Review/update the parameters for this before proceeding.',
                parameters: [
                        string(defaultValue: MAIL_LIST_SUCCESS_DEFAULT.join(','), description: 'Who to email if the upgrade succeeds. ', name: 'MAIL_LIST_SUCCESS'),
                        string(defaultValue: MAIL_LIST_FAILURE_DEFAULT.join(','), description: 'Who to email if the upgrade encounters an error. ', name: 'MAIL_LIST_FAILURE'),
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
                deploylib.run("set-yum-repos")
                deploylib.run("pre-check")
            }

            if ( MODE != "automatic" ) {
                input "Are you certain you want to =====>UPGRADE<===== the =====>${CLUSTER_NAME}<===== cluster?"
            }

            stage( "pre-upgrade status" ) {
                echo "Cluster status BEFORE upgrade:"
                deploylib.run("status")
            }

            stage( "storage-migration" ) {
                /**
                 * The openshift-ansible control-plane upgrade playbooks will perform a storage migration.
                 * However, it has had so many problems that retry&skip are necessary features. We therefore
                 * disable it as part of the ugprade and run it as a separate pipeline step.
                 */
                if ( RUN_STORAGE_MIGRATION.toBoolean() ) {
                    deploylib.run("storage-migration")
                }
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
                // This should eventually be replaced by a post-control-plane online-deployer function
                if (UPGRADE_JENKINS_IMAGE_STREAM.toBoolean()) {
                    deploylib.run("update-jenkins-imagestream")
                }
                
                if (UPGRADE_NODES.toBoolean()) {
                    deploylib.run("upgrade-nodes")
                }
            }

            stage ( "upgrade: online-deployer" ) {
                if ( UPGRADE_ONLINE_COMPONENTS.toBoolean()  ) {
                    deploylib.run( "online-deployer" )
                }
                // deployer presently reset jenkins imagestream; that should be fixed soon
                if (UPGRADE_JENKINS_IMAGE_STREAM.toBoolean()) {
                    deploylib.run("update-jenkins-imagestream")
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

            stage( "post-upgrade status" ) {
                POST_STATUS = deploylib.run("status", null, true)
                echo "Cluster status AFTER upgrade:"
                echo POST_STATUS
            }

            stage( "disable maintenance" ) {

                if ( CLUSTER_NAME != "free-int" && CLUSTER_NAME != "free-stg" ) {
                    // Prevent a flood of issues from notifying SRE as soon as cluster comes out of maintenance
                    mail(to: "jupierce@redhat.com, mwoodson@redhat.com, libra-ops@redhat.com",
                            from: "aos-cd@redhat.com",
                            subject: "Need permission to exit maintenance after upgrade: ${CLUSTER_NAME}",
                            body: """Please review zabbix/clear issues and then click proceed. Anyone from CD or SRE with Jenkins credentials is permitted to perform this operation.

Input URL: ${env.BUILD_URL}input

Jenkins job: ${env.BUILD_URL}
""");
                    input "Cluster =====>${CLUSTER_NAME}<===== is ready to come out of upgrade maintenance; SRE should be notified before doing so."

                }

                deploylib.run( "disable-zabbix-maint" )
                deploylib.run( "disable-statuspage" )
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
