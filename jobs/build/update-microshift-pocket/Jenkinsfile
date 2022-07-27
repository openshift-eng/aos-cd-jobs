#!/usr/bin/env groovy

node {
    checkout scm
    buildlib = load( "pipeline-scripts/buildlib.groovy" )
    commonlib = buildlib.commonlib
    commonlib.describeJob("update-microshift-pocket", """https://issues.redhat.com/browse/ART-4221""")

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
                    string(
                        name: 'BUILD_VERSION',
                        description: 'OCP release version',
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Which assembly contains the microshift to sync.',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    choice(
                        name: 'RHEL_TARGET',
                        description: 'Target RHEL version. Required even if NVRA is specified.',
                        choices: [
                            "8",
                            "9",
                        ].join("\n"),
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )
    commonlib.checkMock()

    version = params.BUILD_VERSION
    currentBuild.displayName = "$version"
    mirror_path = "/pockets/microshift/${version}-el${params.RHEL_TARGET}/${params.ASSEMBLY}"
    AWS_S3_SYNC_OPTS='--no-progress'

    ORG_PLASHET_DIR = "microshift-plashet"
    STAGING_PLASHET_DIR = "staging-plashet" // content from the original plashet without the symlinks
    DOOZER_WORKING = "doozer-working"

    commonlib.shell(
        script: """
        set -e
        rm -rf ${ORG_PLASHET_DIR} ${STAGING_PLASHET_DIR} ${DOOZER_WORKING}
        """
    )

    buildlib.doozer("--working-dir ${DOOZER_WORKING} --assembly ${params.ASSEMBLY} --group openshift-${version} config:plashet --base-dir ${ORG_PLASHET_DIR} --name repos --repo-subdir os -i microshift --arch x86_64 unsigned --arch s390x unsigned --arch ppc64le unsigned --arch aarch64 unsigned from-tags -t rhaos-${version}-rhel-${params.RHEL_TARGET}-candidate NOT_APPLICABLE")

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

        # For each RPM in the staging directory, run signing. This is lunacy because
        # rpm --addsign will not run without prompting for a passphrase. It also can't
        # just take this from something like: echo '' | rpm --addsign ...
        # because it reopens /dev/tty before it tries to read the passphase. It will
        # then pass that string on to gpg. This means even something like gpg-agent
        # can't be used.
        # SO, we use 'screen' to create a disconnected session running the command
        # and use 'stuff' to stuff a new line into the stdin of the session.
        screen_name=microshift-rpm
        for rpm in `find ${STAGING_PLASHET_DIR} -name '*.rpm'`; do """ + '''
            echo signing $rpm
            screen -d -m -S $screen_name rpm --addsign $rpm
            sleep 4  # some time to make sure we are at the prompt
            screen -S $screen_name -p 0 -X stuff "^M"
            sleep 4  # wait for rpm to be signed
            set +e
            # rpm -K will throw an error if the key is not in the rpm database; we don't care
            # we just want proof of a key.
            sign_result=`rpm -K $rpm`
            set -e
            echo "$sign_result" | grep -i pgp   # fail if RPM does not appear signed now
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

    withEnv(["https_proxy="]) {
        commonlib.syncRepoToS3Mirror("${STAGING_PLASHET_DIR}/repos/", mirror_path)
    }
    buildlib.cleanWorkspace()
}
