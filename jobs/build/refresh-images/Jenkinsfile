#!/usr/bin/env groovy
final REPO_PREFIX = 'https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/'
final REPOS = [
    REPO_PREFIX + 'aos-unsigned-building.repo',
    REPO_PREFIX + 'aos-unsigned-errata-building.repo',
    REPO_PREFIX + 'aos-signed-building.repo',
    REPO_PREFIX + 'aos-signed-building-betatest.repo'
]
final DEFAULT_REPO = REPOS[0]

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
        subject: "Images have been refreshed: ${OSE_MAJOR}.${OSE_MINOR} ${OSE_GROUP}",
        body: """\
Jenkins job: ${env.BUILD_URL}
${OSE_MAJOR}.${OSE_MINOR}, Group:${OSE_GROUP}, Repo:${OSE_REPO}
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
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "3", defaultValue: '3', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "1\n2\n3\n4\n5\n6\n7", defaultValue: '4', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "base\nall", defaultValue: 'base', description: 'Which group to refresh', name: 'OSE_GROUP'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Optiontal version to use. (i.e. v3.6.173); leave blank to bump', name: 'VERSION_OVERRIDE'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Specific release to use. Must be > 1 (i.e. 2)', name: 'RELEASE_OVERRIDE'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Image to use when FROM rhel; blank will not change', name: 'RHEL'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: REPOS.join('\n'), defaultValue: DEFAULT_REPO, description: 'Which repo to use', name: 'OSE_REPO'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "git@github.com:openshift\ngit@github.com:jupierce\ngit@github.com:jupierce-aos-cd-bot\ngit@github.com:adammhaile-aos-cd-bot", defaultValue: 'git@github.com:openshift', description: 'Github base for repos', name: 'GITHUB_BASE'],
                              [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?.', name: 'MOCK'],
                      ]
             ]]
    )

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "${OSE_MAJOR}.${OSE_MINOR}, Group:${OSE_GROUP}, Repo:${OSE_REPO} MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], MOCK:${MOCK}"

    currentBuild.displayName = "#${currentBuild.number} - ${OSE_MAJOR}.${OSE_MINOR} (${OSE_GROUP})"

    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode" )
    }

    set_workspace()

    def buildlib = load( "pipeline-scripts/buildlib.groovy")
    buildlib.initialize()

    stage( "enterprise-images repo" ) {
        buildlib.initialize_enterprise_images_dir()
    }
    
    OIT_WORKING = "${pwd(tmp:true)}/oit_working/"
    // create working if not exists
    sh "mkdir -p ${OIT_WORKING}"
    //Clear out if previously in use
    sh "rm -rf ${OIT_WORKING}/*"

    stage('Refresh Images') {
        try {
            env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"

            rhel_arg = ""
            if ( RHEL != "" ) {
                rhel_arg = "--rhel ${RHEL}"
            }

            sshagent(['openshift-bot']) {

                update_docker_args = "--bump_release"
                oit_update_docker_args = ""
                if ( VERSION_OVERRIDE != "" ) {
                    if ( OSE_GROUP != "base" ) {
                        error( "You probably don't want to run with VERSION_OVERRIDE if group is not base" )
                    }
                    if ( RELEASE_OVERRIDE == "" ) {
                        error( "RELEASE_OVERRIDE must be specified if VERSION_OVERRIDE is" )
                    }
                    update_docker_args = "--version ${VERSION_OVERRIDE} --release ${RELEASE_OVERRIDE}"
                    oit_update_docker_args = update_docker_args
                }

                sh "kinit -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM"

                /**
                 * By default, do not specify a version or release for oit. This will preserve the version label and remove
                 * the release label. OSBS now chooses a viable release label to prevent conflicting with pre-existing
                 * builds. Let's use that fact to our advantage.
                 */
                buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${OSE_MAJOR}.${OSE_MINOR}'
--include aos3-installation-docker
--optional-include jenkins-slave-base-rhel7-docker
--optional-include jenkins-slave-maven-rhel7-docker
--optional-include jenkins-slave-nodejs-rhel7-docker
distgits:update-dockerfile
  ${oit_update_docker_args}
  --message 'Updating for image refresh'
  --push
  """

              buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${OSE_MAJOR}.${OSE_MINOR}
--include aos3-installation-docker
--optional-include jenkins-slave-base-rhel7-docker
--optional-include jenkins-slave-maven-rhel7-docker
--optional-include jenkins-slave-nodejs-rhel7-docker
distgits:build-images
--push-to-defaults --repo_type signed
"""
                
                
                
                sh "ose_images.sh --user ocp-build update_docker ${rhel_arg} ${update_docker_args} --force --branch rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7 --group ${OSE_GROUP}"
                sh "ose_images.sh --user ocp-build build --branch rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7 --group ${OSE_GROUP} --repo ${OSE_REPO}"
                sh "sudo env \"PATH=${env.PATH}\" ose_images.sh push --branch rhaos-${OSE_MAJOR}.${OSE_MINOR}-rhel-7 --group ${OSE_GROUP}"
                // end ose_images method

            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success()


        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error Refreshing Images: ${OSE_MAJOR}.${OSE_MINOR} ${OSE_GROUP} ${OSE_REPO}",
                    body: """Encoutered an error while running ${env.JOB_NAME}: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        } finally {
            try {
                archiveArtifacts allowEmptyArchive: true, artifacts: "${OIT_WORKING}/*.log"
                archiveArtifacts allowEmptyArchive: true, artifacts: "${OIT_WORKING}/brew-logs/**"
            } catch( aae ) {}
        }

    }
}
