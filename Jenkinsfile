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

def create_passwd_wrapper() {
    sh env.NSS_WRAPPER_PASSWD
        ? "cp ${env.NSS_WRAPPER_PASSWD} passwd"
        : 'echo "jenkins:x:$(id -u):$(id -g)::$HOME:/sbin/nologin" > passwd'
}

def build_and_push(tag, version) {
    def ose_images = [
        "${env.WORKSPACE}/aos-cd-jobs/ose_images/ose_images.sh",
        '--user ocp-build',
        "--branch 'rhaos-${tag}-rhel-7'",
        '--group base',
    ].join(' ')
    def rcm_guest = 'ocp-build@rcm-guest.app.eng.bos.redhat.com'
    def rcm_dir = '/mnt/rcm-guest/puddles/RHAOS'
    def puddle = "${rcm_dir}/conf/atomic_openshift-${tag}.conf"
    sh """\
LD_PRELOAD=libnss_wrapper.so
NSS_WRAPPER_PASSWD=${env.WORKSPACE}/passwd
NSS_WRAPPER_GROUP=/etc/group
export LD_PRELOAD NSS_WRAPPER_PASSWD NSS_WRAPPER_GROUP
kinit -k -t ${env.WORKSPACE}/keytab \
    ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM
t=\$(tito release --yes --test 'aos-${tag}' | awk '/Created task:/{print \$3}')
echo TASK URL: https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=\$t
brew watch-task "\$t"
ssh '${rcm_guest}' 'puddle -b -d -n -s --label=building ${puddle}'
${ose_images} compare_nodocker
${ose_images} update_docker  --force --release 1 --version 'v${version}'
${ose_images} build_container \
    --repo http://file.rdu.redhat.com/tdawson/repo/aos-unsigned-building.repo
sudo ${ose_images} push_images
ssh '${rcm_guest}' 'puddle -b -d ${puddle}'
ssh '${rcm_guest}' '${rcm_dir}/scripts/push-to-mirrors-bot.sh simple ${tag}'
ssh '${rcm_guest}' sh -s '${tag}' '${version}' \
    < '${env.WORKSPACE}/aos-cd-jobs/rcm-guest/publish-oc-binary.sh'
for x in '${version}/'{linux/oc.tar.gz,macosx/oc.tar.gz,windows/oc.zip}; do
    curl --silent --show-error --head \
        "https://mirror.openshift.com/pub/openshift-v3/clients/\$x" \
        | awk '\$2!="200"{print > "/dev/stderr"; exit 1}{exit}'
done
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
            }
        }
        stage('build and push') {
            create_passwd_wrapper()
            dir('aos-cd-jobs') { sh 'git checkout origin/build-scripts' }
            dir(env.GOPATH + '/src/github.com/openshift/ose') {
                // TODO local rpm testing
                sh 'git push --tags'
                def version = version("origin", readFile("origin.spec"))
                // TODO keytab and ssh key as credentials
                def flags = [
                    "-v ${env.HOME}/ocp-build.keytab:${env.WORKSPACE}/keytab",
                    "-v ${env.HOME}/.ssh/id_rsa:${env.HOME}/.ssh/id_rsa",
                ].join(' ')
                image.inside(flags) { build_and_push(OSE_VERSION, version) }
                mail_success(version)
            }
        }
    }
}
