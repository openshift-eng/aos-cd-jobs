//
// Model a remote git repository
//
package com.redhat.art

import com.redhat.art.Version

class GitHubRepository {

    String owner
    String project
    String branch
    String path
    String package_name
    String password
    def pipeline

    GitHubRepository(String owner, String project, String branch=null, String package_name=null) {
        this.owner = owner
        this.project = project
        this.branch = branch
        this.path = project
        this.package_name = package_name ? package_name : project
        this.password = null
        this.pipeline = pipeline
    }

    GitHubRepository(Map init) {
        this.owner = init.owner
        this.project = init.project
        this.branch = init.branch 
        this.path = init.path ? init.path : this.project
        this.package_name = init.package_name ? init.package_name : this.project
        this.password = init.password
        this.pipeline = init.pipeline
    }

    def getRemote() {
        return "git@github.com:${this.owner}/${this.project}.git"
    }

    def getUrl() {
        return "https://github.com/${this.owner}/${this.project}.git"
    }

    def getSpecfile() {
        return package_name + ".spec"
    }

    def getSpecpath() {
        return [path, specfile].join('/')
    }

    /*
     * Retrive the branch list from a remote repository
     * @param repo_url a git@ repository URL.
     * @param pattern a matching pattern for the branch list. Only return matching branches
     *
     * @return a list of branch names.  Removes the leading ref path
     *
     * Requires SSH_AGENT to have set a key for access to the remote repository
     */
    def branches(pattern="") {
        def branch_text = pipeline.sh(
            returnStdout: true,
            script: [
                "git ls-remote ${this.remote} ${pattern}",
                "awk '{print \$2}'",
                "cut -d/ -f3"
            ].join(" | ")
        )
        return branch_text.tokenize("\n")
    }

    /**
     * Retrive a list of release numbers from the OCP remote repository
     * @param repo_url a git@ repository URL.
     * @return a list of OSE release numbers.
     *
     * Get the branch names beginning with 'enterprise-'.
     * Extract the release number string from each branch release name
     * Sort in version order (compare fields as integers, not strings)
     * Requires SSH_AGENT to have set a key for access to the remote repository
     */
    def releases(pattern="enterprise-") {
        // too clever: chain - get branch names, remove prefix, suffix
        def r = this.branches(pattern + '*')
            .collect { it - pattern }
            .findAll { it =~ /^\d+((\.\d+)*)$/ }
            .collect { new Version(it) }
            .sort()

        return r
    }

    def clone() {
        pipeline.sh(
            returnStdout: false,
            script: [
                "git clone",
                branch ? "--branch ${branch}" : "",
                remote,
                path
            ].join(' ')
        )
        pipeline.echo("Cloning repo ${remote}")
    }
    
    def addRemote(remote_name, remote_project) {
        // git remote add ${remote_name} ${remote_spec}
        def remote_spec = "git@github.com:${owner}/${remote_project}.git"
        pipeline.dir(path) {
            pipeline.sh(
                script: "git remote add ${remote_name} ${remote_spec} --no-tags"
            )
        }
    }

    def fetch(remote_name) {
        pipeline.dir(path) {
            pipeline.sh(
                script: "git fetch ${remote_name}"
            )
        }
    }

    def merge(String remote_name, String remote_branch) {
        pipeline.dir(path) {
            pipeline.sh(
                script: "git merge ${remote_name}/${remote_branch}"
            )
        }
    }

    def config(String key, String value) {
        pipeline.dir(path) {
            pipeline.sh "git config ${key} ${value}"
        }
    }

    def set_attribute(String filename, String attrname, String attrvalue) {
        pipeline.dir(path) {
            def gitattributes = ".gitattributes"
            pipeline.sh(
                script: "echo '${filename} ${attrname}=${attrvalue}' >> ${gitattributes}"
            )
        }
    }
}
