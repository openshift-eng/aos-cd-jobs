node {
    checkout scm
    olm_bundles = load('olm_bundles.groovy')
}

pipeline {
    agent any

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        choice(
            name: 'BUILD_VERSION',
            choices: olm_bundles.commonlib.ocpVersions,
            description: 'OCP Version'
        )
        string(
            name: 'ONLY',
            description: '(Optional) List **only** the operators you want '  +
                         'to build, everything else gets ignored.\n'         +
                         'Format: Comma and/or space separated list of brew '+
                         'packages (e.g.: cluster-nfd-operator-container)\n' +
                         'Leave empty to build all (except EXCLUDE, if defined)',
            defaultValue: ''
        )
        string(
            name: 'EXCLUDE',
            description: '(Optional) List the operators you **don\'t** want ' +
                         'to build, everything else gets built.\n'            +
                         'Format: Comma and/or space separated list of brew ' +
                         'packages (e.g.: cluster-nfd-operator-container)\n'  +
                         'Leave empty to build all (or ONLY, if defined)',
            defaultValue: ''
        )
        string(
            name: 'EXTRAS_ADVISORY',
            description: '(Optional) Fetch OLM Operators NVRs from advisory.\n'  +
                         'Leave empty to fetch NVRs from "brew latest-build".\n' +
                         'Bundles won\'t be attached to any advisory if empty.',
            defaultValue: ''
        )
        booleanParam(
            name: 'DRY_RUN',
            description: 'Just show what would happen, without actually executing the steps',
            defaultValue: false
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
                                it.replace('-operator', '-operator-bundle')
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
                expression { bundle_nvrs && ! params.EXTRAS_ADVISORY.isEmpty() }
            }
            steps {
                script {
                    lock("olm_bundle-${params.BUILD_VERSION}") {
                        olm_bundles.attach_bundles_to_extras_advisory(bundle_nvrs, params.EXTRAS_ADVISORY)
                    }
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
    }
}
