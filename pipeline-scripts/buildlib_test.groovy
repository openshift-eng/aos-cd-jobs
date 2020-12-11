#!/usr/bin/groovy


buildlib = load("pipeline-scripts/buildlib.groovy")

buildlib.initialize(IS_TEST_MODE, false)
echo "Initializing build: #${currentBuild.number} - ${BUILD_VERSION}.?? (${BUILD_MODE})"

// define tests for the functions in buildlib.groovy

//
// test_cmp_version - test comparing version strings
//
def test_cmp_version() {
    pass_count = 0
    fail_count = 0
    
    // initial values
    values = [
        "1.2",
        "3.0",
        "3.0.2",
        "3.0.5",
        "3.1",
        "3.10",
        "3.10.1",
        "3.11",
        "5.3",
        "6" // can you do single digit ones?
    ]

    // test "equals"
    expected = 0
    values.each {
        actual = buildlib.cmp_version(it, it)
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo "FAIL: cmp_version(${values[it]}, ${values[it + 1]}) - expected: ${expected}, actual: ${actual}"
        }
    }

    /// test equality of different length versions
    actual = buildlib.cmp_version("3.1", "3.1.0")
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: cmp_version(\"3.1\"}, \"3.1.0\") - expected: ${expected}, actual: ${actual}"
    }

    // test "less than"
    expected = -1
    (0..(values.size() - 2)).each {
        actual = buildlib.cmp_version(values[it], values[it + 1])
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo "FAIL: cmp_version(${values[it]}, ${values[it + 1]}) - expected: ${expected}, actual: ${actual}"
        }
    }

    /// test different length versions
    actual = buildlib.cmp_version("3.1", "3.1.1")
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: cmp_version(\"3.1\"}, \"3.1.1\") - expected: ${expected}, actual: ${actual}"
    }

    // test "greater than"
    expected = 1
    (1..(values.size() - 1)).each {
        actual = buildlib.cmp_version(values[it], values[it - 1])
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo "FAIL: cmp_version(${values[it]}, ${values[it - 1]}) - expected: ${expected}, actual: ${actual}"
        }
    }
    
    // test different length versions
    actual = buildlib.cmp_version("3.1.1", "3.1")
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: cmp_version(\"3.1.1\"}, \"3.1\") - expected: ${expected}, actual: ${actual}"
    }

    if (fail_count == 0) {
        echo "PASS: cmp_versopm() - ${pass_count} tests passed"
    } else {
        echo "FAIL: cmp_version() - ${pass_count} tests passed, ${fail_count} tests failed"
    }
}

def test_eq_version() {
    pass_count = 0
    fail_count = 0

    values = [
        "1.2",
        "3.0",
        "3.0.2",
        "3.0.5",
        "3.1",
        "3.10",
        "3.10.1",
        "3.11",
        "5.3",
        "6" // can you do single digit ones?
    ]

    // test "equals"
    expected = true
    values.each {
        actual = buildlib.eq_version(it, it)
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo "FAIL: eq_version(${values[it]}, ${values[it + 1]}) - expected: ${expected}, actual: ${actual}"
        }
    }

    /// test equality of different length versions
    actual = buildlib.eq_version("3.1", "3.1.0")
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: eq_version(\"3.1\"}, \"3.1.0\") - expected: ${expected}, actual: ${actual}"
    }
    
    /// test equality of different length versions
    actual = buildlib.eq_version("3.1.0", "3.1")
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: eq_version(\"3.1.0\", \"3.1\") - expected: ${expected}, actual: ${actual}"
    }

    expected = false
    (0..(values.size() - 2)).each {
        /// test equality of different length versions
        actual = buildlib.eq_version(values[it], values[it + 1])
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo "FAIL: eq_version(${values[it]}, ${values[it + 1]}) - expected: ${expected}, actual: ${actual}"
        }
    }

    if (fail_count == 0) {
        echo "PASS: eq_version() - ${pass_count} tests passed"
    } else {
        echo "FAIL: eq_version() - ${pass_count} tests passed, ${fail_count} tests failed"
    }
}

//
// Test sorting arrays of version strings made up of decimal numbers separated by dots (.)
//
def test_sort_versions() {
    pass_count = 0
    fail_count = 0
    
    values = ["3.1", "3.9", "3.5.3", "3.5", "3.10", "3.12", "3.1.3", "3.10.1"]

    // sort operates in place.  Make a copy so the initial unsorted list isn't destroyed
    actual = values.collect()
    expected = ["3.1", "3.1.3", "3.5", "3.5.3", "3.9", "3.10", "3.10.1", "3.12"]

    // sort works in-place but also returns the sorted array.  Curious.
    result = buildlib.sort_versions(actual)

    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        echo "FAIL sort_versions() in-place failed: actual = ${actual}, expected: ${expected}"
        fail_count++
    }

    try {
        assert result == expected
        pass_count++
    } catch (AssertionError e) {
        echo "FAIL sort_versions() return value failed: actual = ${actual}, expected: ${expected}"
        fail_count++
    }

    if (fail_count == 0) {
        echo "PASS: sort_versions() - ${pass_count} tests passed"
    } else {
        echo "FAIL: sort_version() - ${pass_count} tests passed, ${fail_count} tests failed"
    }
}

def test_get_build_branches() {
    pass_count = 0
    fail_count = 0

    test_values = [
        'online:int': [
            ['input': '3.9', 'expected': ['origin': 'master', 'upstream': 'master']]
        ],

        'online:stg': [
            ['input': '3.3', 'expected': ['origin': 'stage', 'upstream': 'stage']]
        ],

        'pre-release': [
            ['input': '3.9', 'expected': ['origin': 'enterprise-3.9', 'upstream': 'release-3.9']]
        ],

        'release': [
            ['input': '3.9', 'expected': ['origin': 'enterprise-3.9', 'upstream': null]]
        ]
    ]

    test_values.each { mode, samples ->
        actual = buildlib.get_build_branches(mode, sample['input'])
        try {
            assert actual == expected
            pass_count++
        } catch (AssertionError e) {
            fail_count++
            echo("failed")
        }
    }

    if (fail_count == 0) {
        echo "PASS: validate_build() - ${pass_count} tests passed"
    } else {
        echo "FAIL: validate_build() - ${pass_count} tests passed, ${fail_count} tests failed"
    }
}

def test_dockerfile_url_for() {
    echo "test_dockerfile_url_for"
    def failed = 0
    [
        [url: "spam", branch: null, path: "", expect: ""],
        [url: "git@github.com:spam/eggs.git", branch: "bacon", path: "",
         expect: "https://github.com/spam/eggs/blob/bacon/"],
        [url: "https://github.com/spam/eggs", branch: "bacon", path: "beans",
         expect: "https://github.com/spam/eggs/blob/bacon/beans"],
    ].each { it ->
        def actual = buildlib.dockerfile_url_for(it.url, it.branch, it.path)
        echo "[${it.url}, ${it.branch}, ${it.path}] ->\nexpect ${it.expect}"
        try {
            assert actual == it.expect
        } catch (AssertionError e) {
            echo "actual ${actual}"
            failed++
        }
    }
    if(failed) { error("test_dockerfile_url_for had ${failed} test failures") }
}

def test_dockerfile_notifications(record_log_path) {
    // make sure to provide params.SUPPRESS_EMAIL = true...
    echo "test_dockerfile_notifications"
    buildlib.notify_dockerfile_reconciliations(record_log_path, "4.1")
}

// make this a function module
return this
