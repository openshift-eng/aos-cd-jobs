#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("microshift_sync", """https://issues.redhat.com/browse/ART-5644 https://issues.redhat.com/browse/ART-4221""")

    properties(
        [
            disableResume(),
            disableConcurrentBuilds(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: ''
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Which assembly contains the microshift to sync.',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'SET_LATEST',
                        description: 'Set the latest link to point to this version',
                        defaultValue: true,
                    ),
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Just show what would happen, without actually updating anything on the mirror',
                        defaultValue: false,
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )
    commonlib.checkMock()

    def version = params.BUILD_VERSION
    def assembly = params.ASSEMBLY

    def out = buildlib.doozer("--group=openshift-${version} -r microshift config:read-rpms --yaml",
                              [capture: true]).trim()
    def yaml_data = readYaml(text: out)["microshift"]
    def rhel_targets = yaml_data["rhel_targets"]
    def arches = yaml_data["arches"]

    echo "rhel_targets: ${rhel_targets}"
    echo "arches: ${arches}"

    def set_latest = params.SET_LATEST
    def dry_run = params.DRY_RUN

    def ORG_PLASHET_DIR = "microshift-plashet"
    def STAGING_PLASHET_DIR = "staging-plashet" // content from the original plashet without the symlinks
    def DOOZER_WORKING = "doozer-working"
    def doozerOpts="--working-dir ${DOOZER_WORKING} --group openshift-${version}"

    def slackChannel = slacklib.to(version)

    def build_microshift_plashet = { String name, String el_major ->
        def plashet_arch_args = ''
        for (String arch : arches) {
            plashet_arch_args += " --arch ${arch} unsigned"
        }
        def productVersion = 'NOT_APPLICABLE'
        def brewTag = "rhaos-${version}-rhel-${el_major}-candidate"
        def embargoedBrewTag = "--embargoed-brew-tag rhaos-${version}-rhel-${el_major}-embargoed"
        def cmd = "${doozerOpts} --rpms microshift config:plashet --base-dir ${ORG_PLASHET_DIR} --name ${name} --repo-subdir os -i microshift ${plashet_arch_args} from-tags --brew-tag ${brewTag} ${productVersion} ${embargoedBrewTag} --signing-advisory-mode clean  --signing-advisory-id 0"
        buildlib.doozer(cmd)
    }

    try {
        stage("Initialize") {
            currentBuild.displayName = "$version - $assembly - $rhel_targets - $arches"
            if (dry_run) {
                currentBuild.displayName = '[DRY RUN] ' + currentBuild.displayName
            } else {
                slackChannel.say(":construction: microshift_sync for ${currentBuild.displayName} :construction:")
            }
            if (assembly.startsWith('ec.')) {
                currentBuild.displayName += " - pub mirror"
            }
            if (!arches) {
                error("No arches configured.")
            }
            commonlib.shell(
                script: """
                set -e
                rm -rf ${ORG_PLASHET_DIR} ${STAGING_PLASHET_DIR} ${DOOZER_WORKING}
                """
            )
        }
        stage('Build plashet repos') {
            for (String rhel_target in rhel_targets) {
                def repo_name = "el$rhel_target"
                echo "Building microshift plashet repo for ${repo_name}..."
                build_microshift_plashet(repo_name, rhel_target)
            }
        }
        stage('Sign with ART CI key') {
            echo "Signing with ART CI key..."
            sh(
                """
                set -euo pipefail
                # Copy plashet to a staging directory were without symlinks. This will allow
                # us to modify the file which is otherwise readonly on /mnt/redhat .
                rsync -r --copy-links ${ORG_PLASHET_DIR}/ ${STAGING_PLASHET_DIR}/

                # Delete all the repodata directories which contain the repo metadata since
                # we have to recreate these after signing the RPMs.
                rm -rf `find ${STAGING_PLASHET_DIR} -name 'repodata'`

                # See https://issues.redhat.com/browse/ART-4221 for more information about
                # setting up signing on buildvm.

                # For each RPM in the staging directory, run signing.
                for rpm in `find ${STAGING_PLASHET_DIR} -name '*.rpm'`; do """ + '''
                    echo signing $rpm
                    rpm --addsign $rpm
                    set +e
                    # rpm -K will throw an error if the key is not in the rpm database; we don't care
                    # we just want proof of a key.
                    sign_result=`rpm -K $rpm`
                    set -e
                    echo "$sign_result" | grep -i "digests signatures OK"   # fail if RPM does not appear signed now
                ''' + """
                done

                # Re-generate repodata for each arch
                for rpm_list in `find ${STAGING_PLASHET_DIR} -name 'rpm_list'`; do """ + '''
                    pushd `dirname $rpm_list`
                    createrepo_c -i rpm_list .
                    popd
                ''' + """
                done
                """
            )
        }

        stage('Copy to mirror') {
            def release_name = assembly.startsWith('ec.') | assembly.startsWith('rc.') ? "${version}.0-${assembly}" : assembly
            def client_type = assembly.startsWith('ec.')? 'ocp-dev-preview' : 'ocp'
            for (String rhel_target in rhel_targets) {
                def repo_name = "el$rhel_target"
                echo "Copying ${repo_name} to public mirror..."
                for (arch in arches) {
                    def mirror_src = "${STAGING_PLASHET_DIR}/${repo_name}/${arch}/os"
                    def mirror_path = "/pub/openshift-v4/${arch}/microshift/${client_type}/${release_name}/${repo_name}/os"
                    def latest_path = "/pub/openshift-v4/${arch}/microshift/${client_type}/latest-${version}/${repo_name}/os"
                    withEnv(["https_proxy="]) {
                        commonlib.syncRepoToS3Mirror(mirror_src, mirror_path, true, 10, dry_run)
                        if (set_latest) {
                            commonlib.syncRepoToS3Mirror(mirror_src, latest_path, true, 10, dry_run)
                        }
                    }
                }
            }
            if (!dry_run) {
                slackChannel.say("microshift_sync completes.")
            }
        }

    } catch (err) {
        def msg = """
            *:heavy_exclamation_mark: microshift_sync failed*
            @release-artists Check the build log for more information.
            buildvm job: ${commonlib.buildURL('console')}
            """
        if (!dry_run) {
            slackChannel.say(msg)
        } else {
            echo "[DRY RUN] Sent slack message to ${params.BUILD_VERSION}: ${msg}"
        }
        throw err  // build is considered failed if anything failed
    } finally {
        commonlib.safeArchiveArtifacts([
            "${DOOZER_WORKING}/*.log",
            "${DOOZER_WORKING}/*.yaml",
        ])
        buildlib.cleanWorkspace()
    }
}
