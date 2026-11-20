// Run locally with: groovy tests/rhcos_dry_run_test.groovy
// All Jenkins steps are mocked. No jobs, workers, AWS calls, or Slack calls are used.
def loader = new GroovyClassLoader()
def interruption = loader.parseClass('''
package org.jenkinsci.plugins.workflow.steps
class FlowInterruptedException extends InterruptedException {
    FlowInterruptedException(String message) { super(message) }
}
''')

def makeRosa = { Set shellFailures = [], Set bindingFailures = [], boolean interrupt = false ->
    def bound = []
    def executed = []
    def messages = []
    def current = ''
    def commonlib = [shell: { command ->
        executed.add([destination: current, command: command.toString()])
        if (interrupt) throw interruption.newInstance('cancelled')
        if (current in shellFailures) throw new IllegalStateException('AWS permission denied')
    }]
    def binding = new Binding([
        env: [WORKSPACE: '/workspace'], currentBuild: [number: 1],
        load: { String path -> [commonlib: commonlib, buildlib: [commonlib: commonlib]] },
        usernamePassword: { Map arguments -> arguments },
        withCredentials: { List credentials, Closure body ->
            assert credentials.size() == 1
            def credential = credentials.first()
            assert credential.usernameVariable == 'AWS_ACCESS_KEY_ID'
            assert credential.passwordVariable == 'AWS_SECRET_ACCESS_KEY'
            current = credential.credentialsId.toString().split('_').last()
            bound.add(current)
            if (current in bindingFailures) throw new IllegalStateException('Credential binding failed')
            body()
        },
        echo: { message -> messages.add(message.toString()) },
        error: { message -> throw new IllegalStateException(message.toString()) }
    ])
    def library = new GroovyShell(loader, binding).parse(new File('jobs/build/rhcos_sync/rhcoslib.groovy'))
    library.run()
    [library: library, bound: bound, executed: executed, messages: messages]
}

def successful = makeRosa()
successful.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', true)
assert successful.bound == ['staging', 'production']
assert successful.executed.every { it.command.endsWith('/workspace/meta.json true') }
assert successful.messages.count { it.contains('permission verified') } == 2

for (boolean failBinding : [false, true]) {
    def failure = failBinding ? makeRosa([] as Set, ['staging'] as Set) : makeRosa(['staging'] as Set)
    try {
        failure.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', true)
        assert false: 'A failed validation must fail the dry-run'
    } catch (IllegalStateException expected) {
        assert expected.message.contains('failed for: staging')
    }
    assert failure.bound == ['staging', 'production']
    assert failure.executed.last().destination == 'production'
    assert failure.messages.any { it.contains('ROSA production:') && it.contains('verified') }
}

def bothFailed = makeRosa(['staging', 'production'] as Set)
try {
    bothFailed.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', true)
    assert false
} catch (IllegalStateException expected) {
    assert expected.message.contains('staging, production')
}
assert bothFailed.bound == ['staging', 'production']

for (boolean failBinding : [false, true]) {
    def liveStagingFailure = failBinding ? makeRosa([] as Set, ['staging'] as Set) : makeRosa(['staging'] as Set)
    def failures = liveStagingFailure.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', false)
    assert failures == ['staging']
    assert liveStagingFailure.bound == ['staging', 'production']
    assert liveStagingFailure.executed.last().destination == 'production'
    assert liveStagingFailure.executed.last().command.endsWith('/workspace/meta.json false')
    assert liveStagingFailure.messages.any { it.contains('ROSA staging sync failed') }
}

def liveProductionFailure = makeRosa(['staging', 'production'] as Set)
try {
    liveProductionFailure.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', false)
    assert false
} catch (IllegalStateException expected) {
    assert expected.message == 'AWS permission denied'
}
assert liveProductionFailure.bound == ['staging', 'production']

def cancelled = makeRosa([] as Set, [] as Set, true)
try {
    cancelled.library.rhcosSyncROSAWithCredentials('/workspace/meta.json', true)
    assert false
} catch (InterruptedException expected) {
    assert expected.message == 'cancelled'
}
assert cancelled.bound == ['staging']

// Execute the actual Azure Jenkinsfile with mocked steps and capture generated commands.
for (boolean dryRun : [true, false]) {
    for (boolean shellFailure : [false, true]) {
        def channels = []
        def commands = []
        def commonlib = [
            describeJob: { name, description -> },
            ocpVersionParam: { name, type -> [:] },
            dryrunParam: { description -> [:] },
            mockParam: { -> [:] },
            checkMock: { -> },
            shell: { Map arguments ->
                commands.add(arguments.script.toString())
                if (shellFailure) throw new IllegalStateException('download failed')
            }
        ]
        def binding = new Binding([
            env: [WORKSPACE: '/workspace'], scm: [:],
            params: [DRY_RUN: dryRun, VERSION: '4.22', OPENSHIFT_INSTALLER_GIT_REF: ''],
            load: { path -> [commonlib: commonlib, cleanWorkdir: { dir -> }, cleanWorkspace: { -> }] },
            slacklib: [to: { channel ->
                channels.add(channel)
                [task: { goal, Closure body -> body() }]
            }],
            node: { Closure body -> body() }, timestamps: { Closure body -> body() },
            stage: { name, Closure body -> body() }, checkout: { scm -> },
            properties: { properties -> }, buildDiscarder: { options -> options },
            logRotator: { options -> options }, string: { options -> options },
            disableResume: { -> [:] }, disableConcurrentBuilds: { -> [:] },
            withCredentials: { credentials, Closure body -> body() }
        ])
        def pipeline = new GroovyShell(loader, binding).parse(new File('jobs/build/publish_azure_marketplace/Jenkinsfile'))
        try {
            pipeline.run()
            assert !shellFailure
        } catch (IllegalStateException expected) {
            assert shellFailure
            assert expected.message == 'download failed'
        }
        assert channels == [dryRun ? null : '4.22']
        assert commands
        assert commands.every { it.contains('az storage blob upload') == !dryRun }
    }
}
new GroovyShell(loader).parse(new File('jobs/build/rhcos_sync/Jenkinsfile'))
println 'PASS: both ROSA destinations, live staging and production failures, cancellation, Azure dry-run guards, and rhcos_sync syntax'
