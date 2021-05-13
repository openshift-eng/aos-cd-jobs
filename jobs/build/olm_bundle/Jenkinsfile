node('covscan') {
    checkout scm
    olm_bundles = load('olm_bundles.groovy')
    olm_bundles.commonlib.describeJob("olm_bundle", """
        <h2>Create bundle images for OLM operators</h2>
        <b>Timing</b>: Run by the ocp4 or custom jobs after new builds.
        Should only need humans to run if something breaks.

        This job creates operator bundle images. These are much like operator
        metadata images in that it contains an operator manifest with a CSV.
        However it only represents a single version of that operator, and only
        ever needs to be built once; there is no need to rebuild for release.

        If an extras advisory is provided, bundle images are attached to that advisory.
        Eventually all of this will simply run as part of the release cycle.
    """)
    bundle_nvrs = []
}

pipeline {
    agent { label 'covscan' }

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        choice(
            name: 'BUILD_VERSION',
            choices: olm_bundles.commonlib.ocpVersions,
            description: 'OCP Version',
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
        string(
            name: 'EXTRAS_ADVISORY',
            description: '(Optional) Fetch OLM Operators NVRs from advisory.\n' +
                         'Leave empty to fetch NVRs from "brew latest-build".',
            defaultValue: '',
            trim: true,
        )
        string(
            name: 'METADATA_ADVISORY',
            description: '(Optional) Attach built bundles to given advisory.\n' +
                         'Bundles won\'t be attached to any advisory if empty.',
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
    }

    stages {
        stage('Set build info') {
            steps {
                script {
                    currentBuild.displayName += " (${params.BUILD_VERSION})"
                    currentBuild.description  = "${params.EXTRAS_ADVISORY ?: '-'} "

                    def only = olm_bundles.commonlib.parseList(params.ONLY)
                    def exclude = olm_bundles.commonlib.parseList(params.EXCLUDE)
                    operator_packages = (only ?: olm_bundles.get_olm_operators()) - exclude
                    olm_bundles.buildlib.initialize(false, false)  // ensure kinit
                }
            }
        }
        stage('Make sure advisories belong to a single group') {
            when {
                expression { ! params.EXTRAS_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    olm_bundles.validate_advisories(params.EXTRAS_ADVISORY, params.METADATA_ADVISORY, params.BUILD_VERSION)
                }
            }
        }
        stage('Get advisory builds') {
            when {
                expression { ! params.EXTRAS_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    operator_nvrs = olm_bundles.get_builds_from_advisory(params.EXTRAS_ADVISORY).findAll {
                        nvr -> operator_packages.any { nvr.startsWith(it) }
                    }
                }
            }
        }
        stage('Get latest builds') {
            when {
                expression { params.EXTRAS_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    operator_nvrs = olm_bundles.get_latest_builds(operator_packages)
                }
            }
        }
        stage('Build bundles') {
            when {
                expression { ! operator_nvrs.isEmpty() }
            }
            steps {
                script {
                    lock("olm_bundle-${params.BUILD_VERSION}") {
                        if (params.DRY_RUN) {
                            bundle_packages = operator_packages.collect {
                                it.replace('-operator', '-operator-metadata')
                            }
                            bundle_nvrs = olm_bundles.get_latest_builds(bundle_packages)
                            print(bundle_nvrs.join('\n'))
                            return
                        }
                        bundle_nvrs = olm_bundles.build_bundles(operator_nvrs)
                    }
                }
            }
        }
        stage('Attach bundles to advisory') {
            when {
                expression { bundle_nvrs && ! params.METADATA_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    lock("olm_bundle-${params.BUILD_VERSION}") {
                        olm_bundles.attach_bundles_to_advisory(bundle_nvrs, params.METADATA_ADVISORY)
                    }
                }
            }
        }
        stage('Slack notification to release channel') {
            when {
                expression { bundle_nvrs && ! params.METADATA_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    olm_bundles.slacklib.to(params.BUILD_VERSION).say("""
                    *:heavy_check_mark: olm_bundle*
The following builds were attached to advisory ${params.METADATA_ADVISORY}:
                    ```
                    ${bundle_nvrs.join('\n')}
                    ```
buildvm job: ${olm_bundles.commonlib.buildURL('console')}
                    """)
                }
            }
        }

    }
    post {
        always {
            script {
                olm_bundles.archiveDoozerArtifacts()
            }
        }
        failure {
            script {
                olm_bundles.slacklib.to(params.BUILD_VERSION).say("""
                *:heavy_exclamation_mark: olm_bundle failed*
                buildvm job: ${olm_bundles.commonlib.buildURL('console')}
                """)
            }
        }
    }
}
