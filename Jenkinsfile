// TODO Replace flow control (when available) with:
// https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/
def try_wrapper(failure_func, f) {
    try {
        f.call()
    } catch(err) {
        failure_func(err)
        // Re-throw the error in order to fail the job
        throw err
    }
}

def mail_success(version) {
    def args = [
        to: 'jupierce@redhat.com',
        subject: "[aos-devel] New AtomicOpenShift Puddle for OSE: ${version}",
        body: """\
v${version}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synched to mirrors


Jenkins job: ${env.BUILD_URL}
""",
    ]
    for(x in args) {println "${x.key}: ${x.value}"}
    mail args
}

def mail_failure = { err ->
    def args = [
        to: 'jupierce@redhat.com',
        subject: "Error building OSE: ${OSE_VERSION}",
        body: """\
Encoutered an error while running merge-and-build.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""",
    ]
    for(x in args) {println "${x.key}: ${x.value}"}
    mail args
}

def git_config() {
    sh '''\
git config user.name 'Jenkins CD Merge Bot'
git config user.email 'tdawson@redhat.com'
'''
}

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

// https://issues.jenkins-ci.org/browse/JENKINS-37069
def fix_workspace_label() {
    sh "chcon -Rt svirt_sandbox_file_t '${env.WORKSPACE}'*"
}

def version(type, s) {
    def matcher = s =~ [
        "origin": /Version:\s+([.0-9]+)/,
        "console": /Vendoring origin-web-console commit (.*)/,
    ][type]
    matcher ? matcher[0][1] : null
}

def vendor_console(image, ref) {
    def vc_commit = null
    image.inside {
        vc_commit = sh(
            returnStdout: true,
            script: "cd '${pwd()}'; GIT_REF=${ref} hack/vendor-console.sh")
    }
    vc_commit = version("console", vc_commit)
    sh """\
[ "\$(git status --porcelain)" ] || exit 0
git add pkg/assets/{,java/}bindata.go
git commit --message \
    'Merge remote-tracking branch ${ref}, bump origin-web-console ${vc_commit}'
"""
}

node('buildvm-devops') {
    properties([[
        $class: 'ParametersDefinitionProperty',
        parameterDefinitions: [
            [
                $class: 'hudson.model.StringParameterDefinition',
                defaultValue: '3.5',
                description: 'OSE version branched but not yet released',
                name: 'OSE_MASTER_BRANCHED',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                defaultValue: '3.5',
                description: 'OSE Version',
                name: 'OSE_VERSION',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                name: 'OSE_CREDENTIALS',
                description: 'Credentials for the OSE repository',
                defaultValue: '',
            ],
        ],
    ]])
    try_wrapper(mail_failure) {
        if(OSE_VERSION != OSE_MASTER_BRANCHED) {
            error 'This script only handles building ${OSE_MASTER_BRANCHED}.'
        }
        deleteDir()
        def image = stage('builder image') {
            dir('aos-cd-jobs') {
                checkout scm
                docker.build 'ose-builder', 'builder'
            }
        }
        set_workspace()
        fix_workspace_label()
        def repos = [
            'bindata': 'https://github.com/jteeuwen/go-bindata.git',
            'console': 'https://github.com/openshift/origin-web-console.git',
            'origin': 'https://github.com/openshift/origin.git',
            'ose': 'git@github.com:openshift/ose.git',
        ]
        env.GOPATH = env.WORKSPACE + '/go'
        stage('dependencies') {
            dir(env.GOPATH + '/src/github.com/jteeuwen/go-bindata') {
                git url: repos['bindata']
            }
            image.inside { sh 'go get github.com/jteeuwen/go-bindata' }
        }
        stage('web console') {
            dir(env.GOPATH + '/src/github.com/openshift/origin-web-console') {
                git url: repos['console'], branch: "enterprise-${OSE_VERSION}"
                git_config()
            }
        }
        stage('merge') {
            dir(env.GOPATH + '/src/github.com/openshift/ose') {
                def branch = "enterprise-${OSE_VERSION}"
                def upstream = 'upstream/release-1.5'
                def commit_msg = "Merge remote-tracking branch ${upstream}"
                checkout(
                    $class: 'GitSCM',
                    branches: [[name: "origin/${branch}"]],
                    userRemoteConfigs: [
                        [url: repos['ose'], credentialsId: OSE_CREDENTIALS],
                        [url: repos['origin'], name: 'upstream']])
                git_config()
                sh "git merge '${upstream}' -m '${commit_msg}'"
                vendor_console(image, "enterprise-${OSE_VERSION}")
                image.inside {
                    sh "cd '${pwd()}'; tito tag --accept-auto-changelog"
                }
                mail_success(version("origin", readFile("origin.spec")))
            }
        }
    }
}
