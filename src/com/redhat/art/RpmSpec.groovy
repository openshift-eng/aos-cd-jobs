#!/usr/bin/groovy
package com.redhat.art

// ===========================================================================
//
// Operations on an RPM Spec File
//
// ===========================================================================

class RpmSpec {

    def filename
    def lines
    def pipeline

    def RpmSpec(Map init) {
        this.filename = init.filename
        this.lines = init.lines
        this.pipeline = init.pipeline

    }
    
    def load() {
        lines = pipeline.readFile(filename).tokenize("\n")
    }

    def save() {
        pipeline.writeFile(file: filename, text: body)
    }
    
    String getBody() {
        return lines.join('\n')
    }
    
    String getVersion() {
        // find the line with the Version tag
        def v_line = lines.find { it =~ /^Version: / }
        if (v_line == null) {
            return null
        }

        // extract the version string and return that
        def v_match = v_line =~ /^Version:\s*([.0-9]+)/
        return v_match[0][1].trim()
    }

    void setVersion(String new_version) {
        // find the version line
        def line_no = lines.findIndexOf{ it =~ /^Version: / }
        assert line_no > -1
        
        // replace it with the new version line
        lines[line_no] = "Version: ${new_version}"
    }

    String getRelease() {
        // find the line with the Version tag
        def v_line = lines.find { it =~ /^Release: / }
        if (v_line == null) {
            return null
        }

        // extract the version string and return that
        def v_match = v_line =~ /^Release:\s*([.0-9]+)/
        return v_match[0][1].trim()
    }
    void setRelease(String new_release) {
        // find the version line
        def line_no = lines.findIndexOf{ it =~ /^Release: / }
        assert line_no > -1
        
        // replace it with the new version line
        lines[line_no] = "Release: ${new_release}"        
    }

    String getChangelog(truncate=true) {
        // find the start of the changelog section
        def start = lines.findIndexOf{ it =~ /%changelog/ }

        // the real changelog starts the next line
        if ( start == -1 ) {
            error "no changelog section in spec file"
        }
        // skip the begin tag
        start++ 

        def end = lines[start..-1].findIndexOf { it =~ /^%/ }
        // the changelog ends with the start of another section or EOF
        //def end = lines.size() -1 // lines[start..-1].findIndexOf 
        if (end == -1) {
            end = lines.size()
        }
        // exclude the end tag
        end--

        def changelines = lines[start..end]

        if (truncate && changelines.size() > 100) {
            changelines = changelines[0..99]
            changelines << '....Truncated....'
        }

        return changelines.join('\n')
    }
}
