#!/usr/bin/env groovy

// Expose properties for a parameterized build
properties(
    [
        disableConcurrentBuilds(),
        disableResume(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'MAIL_LIST_FAILURE',
                    $class: 'hudson.model.StringParameterDefinition',
                    description: 'Failure Mailing List',
                    defaultValue: [
                        'jupierce@redhat.com',
                        'brawilli@redhat.com',
                        'mwoodson@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'OPENSHIFT_VERSION',
                    description: 'Openshift Version (matches version in branch name for release builds)',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: '3.9.0'
                ],
                [
                    name: 'OPENSHIFT_RELEASE',
                    description: 'Release version (The release version number)',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: '0.0.0.git.0.1234567.el7'
                ],
                [
                    name: 'YUM_BASE_URL',
                    description: 'Base url for repository.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'https://mirror.openshift.com/enterprise/online-int/latest/x86_64/os/'
                ],
                [
                    name: 'USE_CRIO',
                    description: 'Enable CRIO in Openshift for the AMI build.',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: true
                ],
                [
                    name: 'CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE',
                    description: 'CRIO system container override image.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'docker.io/runcom/cri-o-system-container:v3.8'
                ],
                [
                    name: 'OPENSHIFT_ANSIBLE_CHECKOUT',
                    description: 'openshift-ansible checkout reference. Leave blank to use corresponding OCP release branch.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ''
                ],
                // Mock
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?.',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
            ]
        ]
    ]
)

if ( params.MOCK || env.MOCK == null) {
    error( "Ran in mock mode to pick up any new parameters" )
}

if ( OPENSHIFT_ANSIBLE_CHECKOUT == "" ) {
    OCP_MAJOR = OPENSHIFT_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y.Z
    OCP_MINOR = OPENSHIFT_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y.Z
    OPENSHIFT_ANSIBLE_CHECKOUT = "release-${OCP_MAJOR}.${OCP_MINOR}"
}

def FORM_PAYLOAD = "OPENSHIFT_VERSION=${OPENSHIFT_VERSION}&OPENSHIFT_RELEASE=${OPENSHIFT_RELEASE}&YUM_BASE_URL=${YUM_BASE_URL}&OPENSHIFT_ANSIBLE_CHECKOUT=${OPENSHIFT_ANSIBLE_CHECKOUT}&USE_CRIO=${USE_CRIO}&CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE=${CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE}"

node('openshift-build-1') {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("aws-ami", """
        ------------------------------------------------
        Publish 3.11 AMI to AWS
        ------------------------------------------------
        This job publishes an AMI created for an OCP 3.11 build on AWS.
        At some point it must have been used in testing 3.y builds in AWS.
        It is not clear that anyone uses it for anything now.

       Timing:
       The ocp3 job runs this job when it's complete.
       There's no known reason for a human to run it.
    """)

    try {
        def build_date = new Date().format('yyyyMMddHHmm')
        stage('invoke') {
            currentBuild.displayName = "#${currentBuild.number} - ${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE}"
            echo "Sending payload:\n${FORM_PAYLOAD}"
            def response = httpRequest(
                                authentication: 'cbed7561-b35d-44e9-b15c-67ae0e6cf017',
                                consoleLogResponseBody: true,
                                contentType: 'APPLICATION_FORM',
                                httpMode: 'POST',
                                ignoreSslErrors: true,
                                requestBody: FORM_PAYLOAD,
                                responseHandle: 'NONE',
                                url: 'https://cr.ops.openshift.com:8443/job/images/job/aws-ami/buildWithParameters',
                                validResponseCodes: '201')
        }
    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "${MAIL_LIST_FAILURE}",
                from: 'aos-cicd@redhat.com',
                subject: "Error building aws ami",
                body: """Encountered an error while running build_ami.yml: ${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }
}
