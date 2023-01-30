#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("publish_azure_marketplace", """
    Per https://issues.redhat.com/browse/ART-3669 & https://issues.redhat.com/browse/ART-5907, provide for occasional
    upload of Azure VHD for marketplace.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('VERSION', '4'),
                    string(
                        name: 'OPENSHIFT_INSTALLER_GIT_REF',
                        description: 'If anything other than release-4.x branch HEAD, specify git reference to checkout (e.g. 1c538b8949f3a0e5b993e1ae33b9cd799806fa93) would result in publishing https://github.com/openshift/installer/blob/1c538b8949f3a0e5b993e1ae33b9cd799806fa93/data/data/rhcos-stream.json#L338',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.dryrunParam('Download artifacts, but do not upload'),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    def workDir = "${env.WORKSPACE}/working"
    buildlib.cleanWorkdir(workDir)

    def azureArtifactCoordinate = [
        '4.8': ['path': 'data/data/rhcos-stream.json', 'jq': ['.architectures.x86_64.artifacts.azure.formats."vhd.gz".disk']],
        '4.9': ['path': 'data/data/rhcos-stream.json', 'jq': ['.architectures.x86_64.artifacts.azure.formats."vhd.gz".disk']],
        '4.10': ['path': 'data/data/coreos/rhcos.json', 'jq': ['.architectures.x86_64.artifacts.azure.formats."vhd.gz".disk']],
        '4.11': ['path': 'data/data/coreos/rhcos.json', 'jq': ['.architectures.x86_64.artifacts.azure.formats."vhd.gz".disk']],
        'default': ['path': 'data/data/coreos/rhcos.json', 'jq': ['.architectures.x86_64.artifacts.azure.formats."vhd.gz".disk', '.architectures.aarch64.artifacts.azure.formats."vhd.gz".disk']],
    ]

    stage('upload vhd.gz') {
        slackChannel = slacklib.to(params.VERSION)
        slackChannel.task("Uploading ${params.VERSION} RHCOS VHD for Azure Marketplace") {
            def coordinateKey = 'default'
            if (azureArtifactCoordinate.containsKey(params.VERSION)) {
                coordinateKey = params.VERSION
            }
            def gitRef = "release-${params.VERSION}"
            if (params.OPENSHIFT_INSTALLER_GIT_REF) {
                gitRef = params.OPENSHIFT_INSTALLER_GIT_REF
            }
            def filePath = azureArtifactCoordinate[coordinateKey]['path']
            def jqExpressions = azureArtifactCoordinate[coordinateKey]['jq']
            def rhcosJsonURL = "https://raw.githubusercontent.com/openshift/installer/${gitRef}/${filePath}"
            withCredentials([string(credentialsId: 'azure_marketplace_staging_upload_key', variable: 'ACCESS_KEY')]) {
                for ( jqExpression in jqExpressions ) {
                    commonlib.shell(script:  """
                    pushd ${workDir}
                    echo 'Using file: ${rhcosJsonURL}'
                    echo 'Using jq expression base: ${jqExpression}'
                    VHD_GZ_URL=`curl --fail '${rhcosJsonURL}' | jq '${jqExpression}.location' -r`
                    VHD_SHA=`curl --fail '${rhcosJsonURL}' | jq '${jqExpression}.sha256' -r`
                    """ +
                    '''
                    VHD_GZ_FILE=`basename $VHD_GZ_URL`
                    VHD_SHA_FILE="$VHD_GZ_FILE".sha256
                    echo $VHD_SHA > $VHD_SHA_FILE

                    curl --fail $VHD_GZ_URL > $VHD_GZ_FILE
                    echo Target VHD: $VHD_GZ_FILE
                    ''' + (params.DRY_RUN?"echo Exiting before upload because of DRY_RUN": '''
                                    az storage blob upload -f $VHD_SHA_FILE --container-name rhcos --account-name artupload --account-key $ACCESS_KEY
                                    az storage blob upload -f $VHD_GZ_FILE --container-name rhcos --account-name artupload --account-key $ACCESS_KEY
                    ''')
                    )
                }
            }
        }
    }

    buildlib.cleanWorkspace()
}
