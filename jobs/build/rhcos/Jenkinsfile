#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("rhcos", """
        <h2>Triggers and waits for an RHCOS build to complete</h2>
    """)

    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '365',
                    daysToKeepStr: '365')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'ARCHES',
                        description: 'Comma delimited list of arches to target The RHCOS architecture to target.',
                        defaultValue: commonlib.brewArches.join(','),
                        trim: true,
                    ),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}: "
    currentBuild.description = "RHCOS ${params.BUILD_VERSION}\n"
    try {
        def releaseArches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()

        arches = params.ARCHES.split(',')

        kubeconfigs = [
            'x86_64': 'jenkins_serviceaccount_ocp-virt.prod.psi.redhat.com.kubeconfig',
            'ppc64le': 'jenkins_serviceaccount_ocp-ppc.stage.psi.redhat.com',
            's390x': 'jenkins_serviceaccount_legacy_rhcos_s390x.psi.redhat.com',
            'aarch64': 'jenkins_serviceaccount_osbs-aarch64-1.engineering.redhat.com',
            'multi': 'multi_jenkins_serviceaccount_ocp-virt.prod.psi.redhat.com.kubeconfig',
        ]

        // Disabling compose lock for now. Ideally we achieve a stable repo for RHCOS builds in the future,
        // but for now, being this strict is slowing down the delivery of nightlies.
        //lock("compose-lock-${params.BUILD_VERSION}") {
        lock(resource: "rhcos-lock-${params.BUILD_VERSION}", skipIfLocked: true) {  // wait for all to succeed or fail for this version before starting more

        // Check if urls.rhcos_release_base.multi is defined in group.yml
        def cmd = "doozer -g openshift-${params.BUILD_VERSION} config:read-group urls.rhcos_release_base.multi --default ''"
        def multi_builds_enabled = !!(commonlib.shell(script: cmd, returnStdout: true).trim())

        if (multi_builds_enabled) {
            currentBuild.displayName += "multi"
            echo "triggering multi builds"
            def jenkins_url = 'https://jenkins-rhcos.apps.ocp-virt.prod.psi.redhat.com'

            try {
                withCredentials([file(credentialsId: kubeconfigs['multi'], variable: 'KUBECONFIG')]) {
                    sh  '''
                        set +x
                        export no_proxy=ocp-ppc.stage.psi.redhat.com,api.ocp-virt.prod.psi.redhat.com,$no_proxy
                        TOKEN_SECRET=$(oc describe sa jenkins | grep 'Tokens:' | tr -s ' ' | cut -d ' ' -f2)
                        TOKEN_DATA=$(oc get secret $TOKEN_SECRET -o=jsonpath={.data.token} | base64 -d)
                        curl -H "Authorization: Bearer $TOKEN_DATA"''' + " ${jenkins_url}/job/build/buildWithParameters --data STREAM=${params.BUILD_VERSION} --data EARLY_ARCH_JOBS=false"
                }
                currentBuild.description += "Success"
            } catch (err) {
                currentBuild.description += "Failure"
                currentBuild.result = "UNSTABLE"
            }
        } else {
            echo "Multi builds are not enabled. Triggering individual builds"
            currentBuild.displayName += "${params.ARCHES}"

            timestamps {
                def archJobs = [:]
                for (arch in arches) {
                    def jobArch = arch.trim() // make sure we use a locally scoped variable
                    if (!releaseArches.contains(jobArch)) {
                        echo "Skipping ${jobArch} since ${params.BUILD_VERSION} only supports ${releaseArches}"
                        continue
                    }
                    archJobs["trigger-${jobArch}"] = {
                        try {
                            lock(label: "rhcos-build-capacity-${jobArch}", quantity: 1) { // cluster capacity limited per arch
                                withCredentials([file(credentialsId: kubeconfigs[jobArch], variable: 'KUBECONFIG')]) {
                                    // the squid proxy inhibits communication to some RHCOS clusters, so augment no_proxy
                                    sh  'export no_proxy=ocp-ppc.stage.psi.redhat.com,api.ocp-virt.prod.psi.redhat.com,$no_proxy\n' +
                                        "oc project\n" +
                                        "BUILDNAME=`oc start-build -o=name buildconfig/rhcos-${params.BUILD_VERSION}`\n" +
                                        'echo Triggered $BUILDNAME\n' +
                                        'for i in {1..240}; do\n' +
                                        '   PHASE=`oc get $BUILDNAME -o go-template=\'{{.status.phase}}\'`\n' +
                                        '   echo Current phase: $PHASE\n' +
                                        '   if [[ "$PHASE" == "Complete" ]]; then\n' +
                                        '       oc logs $BUILDNAME\n' +
                                        '       exit 0\n' +
                                        '   fi\n' +
                                        '   if [[ "$PHASE" == "Failed" || "$PHASE" == "Cancelled" || "$PHASE" == "Error" ]]; then\n' +
                                        '       oc logs $BUILDNAME\n' +
                                        '       exit 1\n' +
                                        '   fi\n' +
                                        '   sleep 60\n' +
                                        'done\n' +
                                        'oc logs $BUILDNAME\n' +
                                        'echo Timed out waiting for build to complete..\n' +
                                        'exit 2\n'
                                }
                            }
                            currentBuild.description += "${jobArch} Success\n"
                        } catch (err) {
                            currentBuild.description += "${jobArch} Failure\n"
                            currentBuild.result = "UNSTABLE"
                        }
                    }
                }
                parallel archJobs
            }
        }}
    } finally {
    }
}
