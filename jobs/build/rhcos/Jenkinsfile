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
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'ARCHES',
                        description: '(Legacy pipeline only) List of architectures to build for RHCOS.',
                        defaultValue: commonlib.brewArches.join(','),
                        trim: true,
                    ),
                    booleanParam(
                        name: 'NEW_BUILD',
                        description: '(Multi pipeline only) Request a new build from the RHCOS pipeline even when it finds no changes from the last.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'IGNORE_RUNNING',
                        description: '(Multi pipeline only) Request a build from the RHCOS pipeline even if one is already in progress (instead of aborting like usual). Still only one runs at a time. Only for use by humans, really, and you probably want NEW_BUILD with this.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: "DRY_RUN",
                        description: "Take no action, just echo what the job would have done.",
                        defaultValue: false
                    ),
                    commonlib.artToolsParam(),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}: "

    if (currentBuild.description == null) {
        currentBuild.description = ""
    }
    currentBuild.description += "RHCOS ${params.BUILD_VERSION}\n"
    skipBuild = true  // global variable to track if we skip the remote build

    try {
        def releaseArches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()

        arches = commonlib.parseList(params.ARCHES)

        kubeconfigs = [
            'x86_64': 'jenkins_serviceaccount_ocp-virt.prod.psi.redhat.com.kubeconfig',
            'ppc64le': 'jenkins_serviceaccount_ocp-ppc.stage.psi.redhat.com',
            's390x': 'jenkins_serviceaccount_legacy_rhcos_s390x.psi.redhat.com',
            'aarch64': 'jenkins_serviceaccount_osbs-aarch64-1.engineering.redhat.com',
            'multi': 'rhcos--prod-pipeline_jenkins_api-prod-stable-spoke1-dc-iad2-itup-redhat-com',
        ]

        if (params.BUILD_VERSION in ["4.15", "4.16", "4.17", "4.18", "4.19"]) {
            kubeconfigs['multi'] = 'multi_jenkins_serviceaccount_ocp-virt.prod.psi.redhat.com.kubeconfig'
        }

        // Disabling compose lock for now. Ideally we achieve a stable repo for RHCOS builds in the future,
        // but for now, being this strict is slowing down the delivery of nightlies.
        //lock("compose-lock-${params.BUILD_VERSION}") {
        def lockval = params.DRY_RUN ? "rhcos-lock-${params.BUILD_VERSION}-dryrun" : "rhcos-lock-${params.BUILD_VERSION}"
        lock(resource: lockval, skipIfLocked: true) {  // wait for all to succeed or fail for this version before starting more
            skipBuild = false

            // Check if urls.rhcos_release_base.multi is defined in group.yml
            def cmd = "doozer -g openshift-${params.BUILD_VERSION} config:read-group urls.rhcos_release_base.multi --default ''"
            def multi_builds_enabled = !!(commonlib.shell(script: cmd, returnStdout: true).trim())

            if (multi_builds_enabled) {
                currentBuild.displayName += "multi"
                echo "triggering multi builds"
                buildlib.init_artcd_working_dir()

                def dryrun = params.DRY_RUN ? '--dry-run' : ''
                def run_multi_build = {
                    withCredentials([file(credentialsId: kubeconfigs['multi'], variable: 'KUBECONFIG')]) {
                        // we want to see the stderr as it runs, so will not capture with commonlib.shell;
                        // but somehow it is buffering the stderr anyway and [lmeyer] cannot figure out why.
                        text = sh(returnStdout: true, script: """
                              no_proxy=api.ocp-virt.prod.psi.redhat.com,\$no_proxy \\
                              artcd ${dryrun} --config=./config/artcd.toml build-rhcos --version=${params.BUILD_VERSION} \\
                                --ignore-running=${params.IGNORE_RUNNING} --new-build=${params.NEW_BUILD}
                        """)
                        echo text
                        if (params.DRY_RUN) {
                            skipBuild = true
                            return
                        }
                        data = readJSON text: text
                        if (data["action"] == "skip") {
                            skipBuild = true
                        } else {
                            if (data["builds"].any { !(it["result"] in ["SUCCESS", null]) }) {
                                currentBuild.result = "UNSTABLE"
                                currentBuild.displayName += " -- Completed with failure"
                            } else {
                                currentBuild.displayName += " -- Completed"
                            }
                        }
                        for (build in data["builds"]) {
                            status = "${build["url"]} - ${build["result"]} '${build["description"]}'"
                            echo status
                            currentBuild.description += "\n<br>${status}"
                        }
                    }
                }
                try {
                    // succeed or fail, RHCOS team do not want us to kick off builds too often
                    parallel "multi": run_multi_build, "rate-limit": { sleep 60 * 60 * 2 }
                } catch (err) {
                    currentBuild.displayName += " -- Failed"
                    echo "Failure: ${err}"
                    currentBuild.result = "FAILURE"
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
                                        sh  'export no_proxy=ocp-ppc.stage.psi.redhat.com,api.s390x.psi.redhat.com,api.ocp-virt.prod.psi.redhat.com,$no_proxy\n' +
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
        }
        if (skipBuild) {
            currentBuild.displayName += " -- Skipped"
            currentBuild.description += " -- skipped (build already in progress)"
            currentBuild.result = "ABORTED"
        }
    } finally {
    }
}
