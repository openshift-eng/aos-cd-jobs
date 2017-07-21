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
    mail(
        to: 'jupierce@redhat.com',
        subject: "[aos-devel] New AtomicOpenShift Puddle for OSE: ${version}",
        body: """\
v${version}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synched to mirrors


Jenkins job: ${env.BUILD_URL}
""");
}

def mail_failure = { err ->
    mail(
        to: 'jupierce@redhat.com',
        subject: "Error building OSE: ${OSE_VERSION}",
        body: """\
Encoutered an error while running merge-and-build.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""");
}

def git_merge(branch, commit, commit_msg, merge_opts = '') {
    sh("""\
git config user.name jenkins
git config user.email jenkins@example.com
git checkout ${branch}
git merge ${merge_opts} '${commit}' -m '${commit_msg}'
""")
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

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

node('openshift-build-1') {
    properties([[
        $class: 'ParametersDefinitionProperty',
        parameterDefinitions: [
            [
                $class: 'hudson.model.StringParameterDefinition',
                defaultValue: '',
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
        deleteDir()
        def image = null
        stage('builder image') {
            dir('aos-cd-jobs') {
                checkout scm
                image = docker.build 'ose-builder', 'builder'
            }
        }
        set_workspace()
        fix_workspace_label()
        stage('dependencies') {
            env.GOPATH = env.WORKSPACE + '/go'
            dir(env.GOPATH + '/src/github.com/jteeuwen/go-bindata') {
                git url: 'https://github.com/jteeuwen/go-bindata.git'
            }
            image.inside {
                sh 'go get github.com/jteeuwen/go-bindata'
            }
        }
        stage('web console') {
            dir(env.GOPATH + '/src/github.com/openshift/origin-web-console') {
                git url: 'https://github.com/openshift/origin-web-console.git'
                git_merge(
                    'master', "origin/enterprise-${OSE_VERSION}",
                    "Merge master into enterprise-${OSE_VERSION}")
            }
        }
        stage('merge') {
            dir(env.GOPATH + '/src/github.com/openshift/ose') {
                checkout(
                    $class: 'GitSCM',
                    branches: [[name: 'refs/remotes/origin/master']],
                    extensions:
                        [[$class: 'LocalBranch', localBranch: 'master']],
                    userRemoteConfigs: [
                        [
                            name: 'upstream',
                            url: 'https://github.com/openshift/origin.git',
                        ],
                        [
                            name: 'origin',
                            url: 'git@github.com:openshift/ose.git',
                            credentialsId: OSE_CREDENTIALS,
                        ],
                    ])
                git_merge(
                    'master', 'upstream/master',
                    'Merge remote-tracking branch upstream/master',
                    '--strategy-option=theirs')
            }
            image.inside {
                sh '''\
cd "$GOPATH/src/github.com/openshift/ose"
GIT_REF=master COMMIT=1 hack/vendor-console.sh
tito tag --accept-auto-changelog
'''
            }
            mail_success(version(
                "${env.GOPATH}/src/github.com/openshift/ose/origin.spec"))
        }
    }
}
