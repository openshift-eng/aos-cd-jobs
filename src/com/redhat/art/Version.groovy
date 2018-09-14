#!/usr/bin/groovy
package com.redhat.art

// ===========================================================================
//
// Version Strings and Operations
//
// ===========================================================================

class Version implements Comparable<Version>{
    def v_array

    def Version(String v_in) {
        v_array = v_in.tokenize('.').collect { it as int }
    }

    def Version(Version model) {
        v_array = model.v_array.collect()
    }

    def Version(o_array) {
        v_array = o_array.collect()
    }

    @NonCPS
    int compareTo(Version other) {

        // make a copy so you can change it safely
        def a = v_array.collect()
        def b = other.v_array.collect()

        // pad one if necessary with zeros
        def max_size = Math.max(a.size(), b.size())
        while (a.size() < max_size) { a << 0 }
        while (b.size() < max_size) { b << 0 }

        // zip the two arrays together so matching elements are together
        def t = [a, b].transpose()

        // check each pair until all are exhausted.
        for (f in t) {
            def cmp = f[0] <=> f[1]
            if (cmp != 0) { return cmp }
        }
        return 0
    }

    @NonCPS
    String toString() {
        return v_array.collect{ it as String }.join('.')
    }

    // Major number property
    void setMajor(int m) { v_array[0] = m }
    int getMajor() { return v_array[0] }

    // Minor number property
    void setMinor(int m) { v_array[1] = m }
    int getMinor() { return v_array[1] }

    // Revision number property
    void setRevision(int m) { v_array[1] = m }
    int getRevision() { return v_array[2] }

    // Major/Minor number string

    String getMajorminor() {
        return v_array[0..1].collect { it as String }.join('.')
    }

    @NonCPS
    Version incrMajor() {
        assert v_array.size() >= 1 :
            "version string must have >= 1 fields. actual: ${v_array.size()}"
        def new_v_array = v_array.collect()

        new_v_array[0]++
        // reset the remaining fields to 0
        if (new_v_array.size() > 1) {
            for (i in 1..(new_v_array.size()-1)) {
                new_v_array[i] = 0
            }
        }
        return new Version(new_v_array)
    }

    @NonCPS
    Version incrMinor() {
        assert v_array.size() >= 2 :
            "version string must have >= 2 fields. actual: ${v_array.size()}"
        def new_v_array = v_array.collect()
        new_v_array[1]++
        if (new_v_array.size() > 2) {
            for (i in 2..(new_v_array.size()-1)) {
                new_v_array[i] = 0
            }
        }
        
        return new Version(new_v_array)
    }

    @NonCPS
    Version incrRevision() {
        assert v_array.size() >= 3 :
            "version string must have >= 3 fields. actual: ${v_array.size()}"
        def new_v_array = v_array.collect()
        new_v_array[2]++
        if (new_v_array.size() > 3) {
            for (i in 3..(new_v_array.size()-1)) {
                new_v_array[i] = 0
            }
        }
        return new Version(new_v_array)
    }
}
