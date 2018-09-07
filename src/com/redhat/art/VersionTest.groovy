#!/usr/bin/groovy
//package com.redhat.art

import com.redhat.art.Version

class VersionTest extends GroovyTestCase {
    def env
    
    def VersionTest(pipeline_env=null) {
        env = pipeline_env
    }
    
    void testConstructorString() {
        def vs = new Version('3.2.1')

        def expected = [3, 2, 1]
        def actual = vs.v_array

        assertEquals(actual, expected)
    }

    void testConstructorVersion() {
        def vs0 = new Version('3.2.1')
        def vs1 = new Version(vs0)

        def expected = [3, 2, 1]
        def actual = vs1.v_array

        assertEquals(actual, expected)
    }
    
    void testConstructorVersionStrin() {
        def v_array = [3, 2, 1]
        def vs1 = new Version(v_array)

        def expected = [3, 2, 1]
        def actual = vs1.v_array

        assertEquals(actual, expected)
    }

    void testCompareTo() {

        def inputs = [
            [
                testValue: new Version('3.2.1'),
                greater: [
                    new Version('3.2.1.1'),
                    new Version('3.2.2'),
                    new Version('3.3.0'),
                    new Version('3.3'),
                    new Version('4.0.0'),
                    new Version('4.0'),
                    new Version('4'),
                ],
                less: [
                    new Version('3.2.0'),
                    new Version('3.1.9.1'),
                    new Version('2.3.0'),
                    new Version('1.0.0'),
                    new Version('3.2'),
                    new Version('2.9'),
                    new Version('2'),                    
                ],
                equal: [
                    new Version('3.2.1'),
                    new Version('3.2.1.0'),
                ]
            ]
        ]

        inputs.each { c -> 
            c.greater.each { t ->  assert t > c.testValue }
            c.less.each { t -> assert t < c.testValue }
            c.equal.each { t -> assert t == c.testValue }
        }
    }

    void testToString() { }

    void testPropertyMajor() { }
    void testPropertyMinor() { }
    void testPropertyRevision() { }

    void testPropertyMajorMinor() { }

    void testIncrMajor() { }

    void testIncrMinor() { }

    void testIncrRevision() { }
}

// mock the NonCPS annotation for groovy testing
@interface NonCPS {}
