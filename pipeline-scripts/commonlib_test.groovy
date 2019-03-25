#!/usr/bin/groovy

cl = load("pipeline-scripts/commonlib.groovy")

// this is testing at its most hacky and disgusting... TODO: use a real framework
def assertEquals(result, expected) {
    assert result == expected : "expected ${expected}; got ${result}"
}
def assertContains(result, expected) {
    assert result.contains(expected) : "expected ${expected} to be in ${result}"
}

// how to run tests? write a job that loads this and runs method(s), then run the job.
// be careful not to merge such test jobs...

def test_shell() {
    assertEquals cl.shell("echo foo"), null  // and no error thrown

    def retval = cl.shell(script: "echo foo >&2; echo bar", returnAll: true)
    echo "${retval}"
    assertEquals retval.stderr.trim(), "foo"
    assertEquals retval.stdout.trim(), "bar"
    assertEquals retval.returnStatus, 0

    retval = cl.shell(script: "borky bork bork", returnAll: true)
    echo "${retval}"
    assertEquals retval.returnStatus, 1 // should be 127 though

    assertEquals cl.shell(script: "borky bork bork", returnStatus: true), 1 // should be 127 though
    assertEquals cl.shell(script: "echo bar", returnStdout: true).trim(), "bar"

    try {
        cl.shell(returnStdout: true, script: "borky bork bork  # padding this to make it long enough that it gets truncated")
        assert false : "should throw err"
    } catch(err) {
        echo "message is:\n${err.getMessage()}"  // doesn't show useless exception class
        assertContains "${err}", "borky bork bork"
        assertContains "${err}", "command not found"
        assertContains "${err}", "..."
    }

    try {
        cl.shell("for i in 1 2 3 4; do echo \$i >&2; done; borkinate")
        assert false : "should throw err"
    } catch(err) {
        echo "message is:\n${err.getMessage()}"  // doesn't show useless exception class
        assertContains "${err}", "see full archive"
        assert !err.getMessage().contains("1\n2") : "only three lines of stderr should be included"
    }

}

return this
