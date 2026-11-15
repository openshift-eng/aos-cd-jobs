// Run from the repository root with: groovy scheduled-jobs/build/update-test-assembly/Jenkinsfile_test.groovy

def runScheduler(List configurations, boolean failFetch = false) {
    def builds = []
    def messages = []
    def reads = 0
    def steps = new Binding([
        scm: 'test-scm',
        node: { Closure body -> body() },
        timestamps: { Closure body -> body() },
        checkout: { Object ignored -> },
        load: { String ignored -> [ocpMajorVersions: ['4plus': ['4.12', '4.13', '4.14']]] },
        properties: { Object ignored -> },
        buildDiscarder: { Object options -> options },
        logRotator: { Object options -> options },
        disableConcurrentBuilds: { -> null },
        disableResume: { -> null },
        httpRequest: { Map options ->
            assert options.url == 'https://raw.githubusercontent.com/openshift-eng/ocp-build-data/main/config/automation.yml'
            assert options.validResponseCodes == '200'
            if (failFetch) {
                throw new IOException('Config unavailable')
            }
            [content: 'fixture']
        },
        readYaml: { Map options -> configurations[Math.min(reads++, configurations.size() - 1)] },
        error: { String message -> throw new IllegalStateException(message) },
        echo: { String message -> messages << message },
        string: { Map options -> options },
        booleanParam: { Map options -> options },
        build: { Map options -> builds << options },
    ])
    def failure = null
    try {
        new GroovyShell(steps).evaluate(new File('scheduled-jobs/build/update-test-assembly/Jenkinsfile'))
    } catch (Exception ex) {
        failure = ex
    }
    [builds: builds, messages: messages, reads: reads, failure: failure]
}

def frozen = runScheduler([[freeze_automation: true]])
assert frozen.failure == null
assert frozen.builds.empty
assert frozen.messages.any { it.contains('all groups are frozen') }

def unfrozen = runScheduler([[freeze_automation: false]])
assert unfrozen.failure == null
assert unfrozen.builds.size() == 3
assert unfrozen.reads == 3
assert unfrozen.builds.collect { it.parameters.find { it.name == 'BUILD_VERSION' }.value } == ['4.12', '4.13', '4.14']
assert unfrozen.builds.every { it.parameters.find { it.name == 'IGNORE_LOCKS' }.value == true }

def freezeDuringLoop = runScheduler([[freeze_automation: false], [freeze_automation: true]])
assert freezeDuringLoop.failure == null
assert freezeDuringLoop.builds.size() == 1
assert freezeDuringLoop.reads == 2

for (invalid in [null, [], [:], [freeze_automation: 'false'], [freeze_automation: 'scheduled']]) {
    def result = runScheduler([invalid])
    assert result.failure instanceof IllegalStateException
    assert result.builds.empty
}

def unavailable = runScheduler([], true)
assert unavailable.failure instanceof IOException
assert unavailable.builds.empty

println 'Passed: frozen, unfrozen, mid-loop freeze, invalid config, and config read failure'
