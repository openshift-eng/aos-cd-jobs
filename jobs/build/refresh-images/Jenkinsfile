#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

def mail_success() {
    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cd@redhat.com",
        replyTo: 'smunilla@redhat.com',
        subject: "Images have been refreshed: ${OSE_MAJOR}.${OSE_MINOR}",
        body: """\
Jenkins job: ${env.BUILD_URL}
${OSE_MAJOR}.${OSE_MINOR}
""");
}

node('openshift-build-1') {
    checkout scm

    // Expose properties for a parameterized build
    properties(
            [   buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '720')),
                [$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "git@github.com:openshift\ngit@github.com:jupierce\ngit@github.com:jupierce-aos-cd-bot\ngit@github.com:adammhaile-aos-cd-bot", defaultValue: 'git@github.com:openshift', description: 'Github base for repos', name: 'GITHUB_BASE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "3", defaultValue: '3', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "1\n2\n3\n4\n5\n6\n7", defaultValue: '4', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'auto', description: 'Optional version to use. (i.e. v3.6.17). Defaults to "auto"', name: 'VERSION_OVERRIDE'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Optional release to use. Must be > 1 (i.e. 2)', name: 'RELEASE_OVERRIDE'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com,bbarcaro@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com,bbarcaro@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?.', name: 'MOCK'],
                              // TODO reenable when the mirrors have the necessary puddles
                              [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Build golden image after building images?', name: 'BUILD_AMI'],
                      ]
             ]]
    )

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "${OSE_MAJOR}.${OSE_MINOR}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], MOCK:${MOCK}"

    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR}"

    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode" )
    }

    set_workspace()

    def buildlib = load( "pipeline-scripts/buildlib.groovy")
    buildlib.initialize()

    stage( "enterprise-images repo" ) {
        buildlib.initialize_enterprise_images_dir()
    }

    // oit_working must be in WORKSPACE in order to have artifacts archived
    OIT_WORKING = "${WORKSPACE}/oit_working"
    //Clear out previous work
    sh "rm -rf ${OIT_WORKING}"
    sh "mkdir -p ${OIT_WORKING}"

    stage('Refresh Images') {
        try {
            try{
                // Clean up old images so that we don't run out of device mapper space
                sh "docker rmi --force \$(docker images  | grep v${OSE_MAJOR}.${OSE_MINOR} | awk '{print \$3}')"
            } catch ( cce ) {
                echo "Error cleaning up old images: ${cce}"
            }

            sshagent(['openshift-bot']) {

                // default to using the atomic-openshift package version
                // unless the caller provides a version and release
                if ( VERSION_OVERRIDE == "auto" ) {
                    oit_update_docker_args = "--version auto --repo-type signed"
                } else {
                    if ( ! VERSION_OVERRIDE.startsWith("v") ) {
                        error("Version overrides must start with 'v'")
                    }
                    oit_update_docker_args = "--version ${VERSION_OVERRIDE}"
                }

                if ( RELEASE_OVERRIDE != "" ) {
                    oit_update_docker_args = "${oit_update_docker_args} --release ${RELEASE_OVERRIDE}"
                }

                sh "kinit -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM"

                /**
                 * By default, do not specify a version or release for oit. This will preserve the version label and remove
                 * the release label. OSBS now chooses a viable release label to prevent conflicting with pre-existing
                 * builds. Let's use that fact to our advantage.
                 */
                buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
images:update-dockerfile
  ${oit_update_docker_args}
  --message 'Updating for image refresh'
  --push
  """

		buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
images:build
--push-to-defaults --repo-type signed
"""

		try {
		    buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
images:verify
--repo-type signed
"""
		} catch ( vererr ) {
		    echo "Error verifying images: ${vererr}"
		    mail(to: "${MAIL_LIST_FAILURE}",
			 from: "aos-cd@redhat.com",
			 subject: "Error Verifying Images During Refresh: ${OSE_MAJOR}.${OSE_MINOR}",
			 body: """Encoutered an error while running ${env.JOB_NAME}: ${vererr}


Jenkins job: ${env.BUILD_URL}
""");
		}
            }

            if(params.BUILD_AMI) {
                // e.g. version_release = ['v3.9.0', '0.34.0.0']
                final version_release = buildlib.oit([
                    "--working-dir ${OIT_WORKING}",
                    "--group openshift-${OSE_MAJOR}.${OSE_MINOR}",
                    '--images openshift-enterprise-docker',
                    '--quiet',
                    'images:print --short {version}-{release}',
                ].join(' '), [capture: true]).split('-')
                buildlib.build_ami(
                    OSE_MAJOR, OSE_MINOR,
                    version_release[0].substring(1), version_release[1],
                    "release-${OSE_MAJOR}.${OSE_MINOR}",
                    MAIL_LIST_FAILURE)
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success()


        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error Refreshing Images: ${OSE_MAJOR}.${OSE_MINOR}",
                    body: """Encoutered an error while running ${env.JOB_NAME}: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            try {
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/*.log"
                archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/brew-logs/**"
            } catch( aae ) {}
        }

    }
}
