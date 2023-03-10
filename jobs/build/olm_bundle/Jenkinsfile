node('covscan') {
    checkout scm
    buildlib = load('pipeline-scripts/buildlib.groovy')
    commonlib = buildlib.commonlib
    slacklib = commonlib.slacklib
    commonlib.describeJob("olm_bundle", """
        <h2>Create bundle images for OLM operators</h2>
        <b>Timing</b>: Run by the ocp4 or custom jobs after new builds.
        Should only need humans to run if something breaks.

        This job creates operator bundle images. These are much like operator
        metadata images in that it contains an operator manifest with a CSV.
        However it only represents a single version of that operator, and only
        ever needs to be built once; there is no need to rebuild for release.
    """)
    bundle_nvrs = []
}

String[] operator_nvrs = []
String[] only = []
String[] exclude = []

pipeline {
    agent { label 'covscan' }

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        choice(
            name: 'BUILD_VERSION',
            choices: commonlib.ocpVersions,
            description: 'OCP Version',
        )
        string(
            name: 'ASSEMBLY',
            description: 'Assembly name.',
            defaultValue: "stream",
            trim: true,
        )
        string(
            name: 'DOOZER_DATA_PATH',
            description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
            trim: true,
        )
        string(
            name: 'DOOZER_DATA_GITREF',
            description: '(Optional) Doozer data path git [branch / tag / sha] to use',
            defaultValue: "",
            trim: true,
        )
        string(
            name: 'OPERATOR_NVRS',
            description: '(Optional) List **only** the operator NVRs you want to build bundles for, everything else gets ignored. The operators should not be mode:disabled/wip in ocp-build-data',
            defaultValue: "",
            trim: true,
        )
        string(
            name: 'ONLY',
            description: '(Optional) List **only** the operators you want '  +
                         'to build, everything else gets ignored.\n'         +
                         'Format: Comma and/or space separated list of brew '+
                         'packages (e.g.: cluster-nfd-operator-container)\n' +
                         'Leave empty to build all (except EXCLUDE, if defined)',
            defaultValue: '',
            trim: true,
        )
        string(
            name: 'EXCLUDE',
            description: '(Optional) List the operators you **don\'t** want ' +
                         'to build, everything else gets built.\n'            +
                         'Format: Comma and/or space separated list of brew ' +
                         'packages (e.g.: cluster-nfd-operator-container)\n'  +
                         'Leave empty to build all (or ONLY, if defined)',
            defaultValue: '',
            trim: true,
        )
        booleanParam(
            name: 'FORCE_BUILD',
            description: 'Rebuild bundle containers, even if they already exist for given operator NVRs',
            defaultValue: false,
        )
        booleanParam(
            name: 'DRY_RUN',
            description: 'Just show what would happen, without actually executing the steps',
            defaultValue: false,
        )
        booleanParam(
            name: 'MOCK',
            description: 'Pick up changed job parameters and then exit',
            defaultValue: false,
        )
    }

    stages {
        stage('Check mock') {
            steps {
                script {
                    commonlib.checkMock()
                }
            }
        }
        stage('Set build info') {
            steps {
                script {
                    operator_nvrs = commonlib.parseList(params.OPERATOR_NVRS)
                    only = commonlib.parseList(params.ONLY)
                    exclude = commonlib.parseList(params.EXCLUDE)
                    currentBuild.displayName += " (${params.BUILD_VERSION})"

                    if (params.ASSEMBLY && params.ASSEMBLY != "stream") {
                        currentBuild.displayName += " - assembly ${params.ASSEMBLY}"
                    }
                }
            }
        }
        stage('Build bundles') {
            steps {
                script {
                    lock("olm_bundle-${params.BUILD_VERSION}") {
                        def cmd = ""
                        cmd += "--data-path=${params.DOOZER_DATA_PATH}"
                        if (only)
                            cmd += " --images=${only.join(',')}"
                        if (exclude)
                            cmd += " --exclude=${exclude.join(',')}"
                        cmd += " olm-bundle:rebase-and-build"
                        if (params.FORCE_BUILD)
                            cmd += " --force"
                        if (params.DRY_RUN)
                            cmd += " --dry-run"
                        cmd += " -- "
                        cmd += operator_nvrs.join(' ')

                        def doozer_working = "${WORKSPACE}/doozer_working"
                        buildlib.cleanWorkdir(doozer_working)
                        def groupParam = "openshift-${params.BUILD_VERSION}"
                        if (doozer_data_gitref) {
                            groupParam += "@${params.DOOZER_DATA_GITREF}"
                        }
                        def doozer_opts = "--working-dir ${doozer_working} -g '${groupParam}'"

                        timeout(activity: true, time: 60, unit: 'MINUTES') { // if there is no log activity for 1 hour
                            buildlib.doozer("${doozer_opts} ${cmd}")
                            def record_log = buildlib.parse_record_log(doozer_working)
                            def records = record_log.get('build_olm_bundle', [])
                            def bundle_nvrs = []
                            for (record in records) {
                                if (record['status'] != '0') {
                                    throw new Exception("record.log includes unexpected build_olm_bundle record with error message: ${record['message']}")
                                }
                                bundle_nvrs << record["bundle_nvr"]
                            }
                        }
                    }
                    echo "Successfully built:\n${bundle_nvrs.join('\n')}"
                }
            }
        }
    }
    post {
        always {
            script {
                commonlib.safeArchiveArtifacts([
                    "doozer_working/*.log",
                    "doozer_working/*.yaml",
                    "doozer_working/brew-logs/**",
                ])
            }
        }
        failure {
            script {
                if (params.DRY_RUN) {
                    return
                }
                slacklib.to(params.BUILD_VERSION).say("""
                *:heavy_exclamation_mark: olm_bundle failed*
                buildvm job: ${commonlib.buildURL('console')}
                """)
            }
        }
    }
}
