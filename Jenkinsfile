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
        subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}",
        body: """\
Encoutered an error while running merge-and-build.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""");
}

node {
    properties([[
        $class: 'ParametersDefinitionProperty',
        parameterDefinitions: [
            [
                $class: 'hudson.model.StringParameterDefinition',
                defaultValue: '',
                description: 'OSE Major Version',
                name: 'OSE_MAJOR',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                defaultValue: '',
                description: 'OSE Minor Version',
                name: 'OSE_MINOR',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                name: 'OSE_REPO',
                description: 'OSE repository url',
                defaultValue: 'https://github.com/openshift/ose.git',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                name: 'ORIGIN_REPO',
                description: 'Origin repository url',
                defaultValue: 'https://github.com/openshift/origin.git',
            ],
            [
                $class: 'hudson.model.StringParameterDefinition',
                name: 'WEB_CONSOLE_REPO',
                description: 'Origin web console repository url',
                defaultValue:
                    'https://github.com/openshift/origin-web-console.git',
            ],
        ],
    ]])
    stage('Merge and build') {
        try_wrapper(mail_failure) {
            env.GOPATH = env.WORKSPACE + '/go'
            dir(env.GOPATH) { deleteDir() }
            sh 'go get github.com/jteeuwen/go-bindata'
            dir(env.GOPATH + '/src/github.com/openshift/origin-web-console') {
                git url: WEB_CONSOLE_REPO
                sh 'git config user.name jenkins'
                sh 'git config user.email jenkins@example.com'
                sh "git checkout --track origin/enterprise-${OSE_MAJOR}.${OSE_MINOR}"
                sh "git merge master -m 'Merge master into enterprise-${OSE_MAJOR}.${OSE_MINOR}'"
            }
            dir(env.GOPATH + '/src/github.com/openshift/ose') {
                checkout(
                    $class: 'GitSCM',
                    branches: [[name: 'master']],
                    userRemoteConfigs: [
                        [name: 'upstream', url: "${ORIGIN_REPO}"],
                        [name: 'origin', url: "${OSE_REPO}"]])
                sh 'git config user.name jenkins'
                sh 'git config user.email jenkins@example.com'
                sh 'git merge --strategy-option=theirs -m "Merge remote-tracking branch upstream/master" upstream/master'
                def web_console_ref = sh(
                    returnStdout: true,
                    script: "set -o pipefail && GIT_REF=master hack/vendor-console.sh | awk '/Vendoring origin-web-console/{print \$4}'")
                if(sh(
                        script: 'git status --porcelain',
                        returnStdout: true)) {
                    sh 'git add pkg/assets/{,java/}bindata.go'
                    sh "git commit -m 'Merge remote-tracking branch upstream/master, bump origin-web-console ${web_console_ref}'"
                }
                sh 'tito tag --accept-auto-changelog'
                def v = readFile(file: 'origin.spec') =~ /Version:\s+([.0-9]+)/
                mail_success(v[0][1])
            }
        }
    }
}
