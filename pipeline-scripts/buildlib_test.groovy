#!/usr/bin/groovy


buildlib = load("pipeline-scripts/buildlib.groovy")

buildlib.initialize(IS_TEST_MODE)
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

//
// Test the automatic "build mode" selection for different version and release number inputs
//
// The auto_mode() function returns 1 of 4 values:
//   'dev':         The version to build matches the master:HEAD version and is not in the current release set
//   'pre-release': The version matches master:HEAD and a release branch for that version exists
//   'release':     The version matches a release branch but is not the version at master:HEAD
//   null:          The version is neither on a release branch or in master:HEAD
//
def test_auto_mode() {
    pass_count = 0
    fail_count = 0

    releases = ["3.0", "3.1", "3.2"]

    expected = 'dev'
    actual = buildlib.auto_mode("3.3", "3.3", releases)
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: auto_mode(\"3.3\", \"3.3\", ${releases}): actual: ${actual}, expected ${expected}"
    }

    expected = 'pre-release'
    actual = buildlib.auto_mode("3.2", "3.2", releases)
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: auto_mode(\"3.2\", \"3.2\", ${releases}): actual: ${actual}, expected ${expected}"
    }

    expected = 'release'
    actual = buildlib.auto_mode("3.2", "3.3", releases)
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: auto_mode(\"3.2\", \"3.3\", ${releases}): actual: ${actual}, expected ${expected}"
    }

    expected = null
    actual = buildlib.auto_mode("3.4", "3.3", releases)
    try {
        assert actual == expected
        pass_count++
    } catch (AssertionError e) {
        fail_count++
        echo "FAIL: auto_mode(\"3.4\", \"3.3\", ${releases}): actual: ${actual}, expected ${expected}"
    }

    if (fail_count == 0) {
        echo "PASS: auto_mode() - ${pass_count} tests passed"
    } else {
        echo "FAIL: auto_mode() - ${pass_count} tests passed, ${fail_count} tests failed"
    }
}

// make this a function module
return this
