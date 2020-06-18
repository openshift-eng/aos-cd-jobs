#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'COMPONENTS',
                        description: '(REQUIRED) Brew component name',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "logging-fluentd-container"
                    ],
                    [
                        name: 'ADVISORY',
                        description: '(REQUIRED) Image release advisory number.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'RCM_GUEST',
                        description: 'Details of RCM GUEST',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "ocp-build@rcm-guest.app.eng.bos.redhat.com:/mnt/rcm-guest/ocp-client-handoff/"
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    buildlib.initialize()
    buildlib.cleanWorkdir(env.WORKSPACE)

    try {
        sshagent(['openshift-bot']) {
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0
            if (advisory == 0) {
                error "Need to provide an ADVISORY ID"
            }
            def components = params.COMPONENTS.replaceAll(',', ' ').split(' ')
            def filename = "tarball-source-output.txt"
            def outdir = "/mnt/nfs/home/jenkins/container-sources/"
            def rcm_guest = params.RCM_GUEST.toString()
            currentBuild.description = "tarball: ${components}"

            stage("elliott tarball-source") {
                component_args = ""
                components.each {
                    component_args += "--component ${it}"
                }
                buildlib.elliott """
                    tarball-sources create
                    --out-dir=${outdir}
                    --force
                    ${component_args}
                    ${advisory} > ${filename}
                """
            }

            stage("rsync") {
                cmd = "rsync -avz --no-perms --no-owner --no-group ${outdir} ${rcm_guest}"
                res = commonlib.shell(
                    script: cmd,
                    returnAll: true
                )
                if(res.returnStatus != 0 || res.stderr != "") {
                    error "rsync executing failed..."
                }
            }

            stage("file ticket to RCM") {
                // use awk to print out the lines that contain ${advisory}
                // sth like this:
                // RHEL-7-OSE-4.2/${advisory}/release/logging-fluentd-container-v4.2.26-202003230335.tar.gz 
                cmd = """awk '/${advisory}/ { save=\$0 }END{ print save }' ${filename}"""
                verify = commonlib.shell(
                        script: cmd,
                        returnStdout: true
                )

                cmd = """echo '${verify}' |awk -F '-v' '{print \$2}' |awk -F '-' '{print \$1}' """
                version = commonlib.shell(
                        script: cmd,
                        returnStdout: true
                )

                currentBuild.description += " ocp ${version}"
                description = """Hi RCM,
                    The OpenShift ART team needs to provide sources for `${components}` in https://errata.devel.redhat.com/advisory/${advisory}

                    The following sources are uploaded to ${rcm_guest}

                    ${verify}

                    Attaching source tarballs to be published on ftp.redhat.com as in https://projects.engineering.redhat.com/browse/RCMTEMPL-6549
                    """
                withCredentials([usernamePassword(
                    credentialsId: 'rcm-jira-openshift-art-automation',
                    usernameVariable: 'JIRA_USERNAME',
                    passwordVariable: 'JIRA_PASSWORD',
                )]) {
                    withEnv(["ds=${description}"]){
                        cmd = "jirago -password=${JIRA_PASSWORD} -type \"Ticket\" -summary=\"OCP Tarball sources\" -description=\"${ds}\""
                        jira = commonlib.shell(
                            script: cmd,
                            returnStdout: true
                        )
                    }
                }
                echo "sucessfully run cmd: ${jira}"
            }
        }

    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Tarball sources",
            body: "Encountered an error while running OCP Tarball sources: ${err}");
        currentBuild.description = "Error while running OCP Tarball sources:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}
