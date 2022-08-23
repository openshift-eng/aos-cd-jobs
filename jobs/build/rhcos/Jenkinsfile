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
    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}: ${params.ARCHES}"
    currentBuild.description = "RHCOS ${params.BUILD_VERSION}\n"
    try {
        def releaseArches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()

        arches = params.ARCHES.split(',')

        kubeconfigs = [
            'x86_64': 'jenkins_serviceaccount_ocp-virt.prod.psi.redhat.com.kubeconfig',
            'ppc64le': 'jenkins_serviceaccount_p8.psi.redhat.com.kubeconfig',
            's390x': 'jenkins_serviceaccount_osbs-s390x-3.prod.engineering.redhat.com.kubeconfig',
            'aarch64': 'jenkins_serviceaccount_osbs-aarch64-1.engineering.redhat.com',
        ]

        // Disabling compose lock for now. Ideally we achieve a stable repo for RHCOS builds in the future,
        // but for now, being this strict is slowing down the delivery of nightlies.
        //lock("compose-lock-${params.BUILD_VERSION}") {
        lock(resource: "rhcos-lock-${params.BUILD_VERSION}", skipIfLocked: true) {  // wait for all to succeed or fail for this version before starting more
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
                                sh  'export no_proxy=p8.psi.redhat.com,api.ocp-virt.prod.psi.redhat.com,$no_proxy\n' +
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
        }
    } finally {
    }
}
