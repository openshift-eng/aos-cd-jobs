package com.redhat.art

import com.redhat.art.GitHubRepository
import com.redhat.art.RpmSpec

class Rpm {

    GitHubRepository repo
    String collection
    def pipeline

    def Rpm(Map init) {
        this.repo = init.repo
        this.collection = init.collection
        this.pipeline = init.pipeline
    }

    String getSpecpath() {
        return repo.specpath
    }

    RpmSpec getSpec() {
        return new RpmSpec([filename: repo.specpath, pipeline: pipeline])
    }

    def tag(Map args) {

        String version_spec
        if (args.version && args.release) {
            version_spec = "--use-version ${args.version} --use-release ${args.release}"
        } else {
            version_spec = "--keep-version"
        }

        pipeline.echo("Tagging with ${version_spec}")

        def build_cmd = [
            "tito tag",
            (args.debug ? '--debug' : ''),
            '--accept-auto-changelog',
            version_spec
        ].join(' ')

        if (collection) {
            build_cmd = "scl enable ${collection} '${build_cmd}'"
        }

        pipeline.echo("tagging with cli: ${build_cmd}")

        pipeline.dir(repo.path) {
            pipeline.sh(
                script: build_cmd
            )
        }
    }

    def build(destination="./BUILD", debug=false) {

        def build_cmd = [
            "tito build",
            (debug ? '--debug' : ''),
            '--offline',
            '--rpm',
            '--output', destination,
        ].join(' ')

        if (collection) {
            build_cmd = "scl enable ${collection} '${build_cmd}'"
        }

        pipeline.dir(repo.path) {
            pipeline.sh(
                script: build_cmd
            )
        }
    }

    def release(scratch=true, debug=false) {
        def s = spec
        s.load()
        def version = new Version(s.version)
        pipeline.dir(repo.path) {
            def tito_output = pipeline.sh(
                returnStdout: true,
                script: [
                    'tito release',
                    (debug ? '--debug' : ''),
                    '--yes',
                    '--test',
                    (scratch ? '--scratch' : ''),
                    "aos-${version.majorminor}"
                ].join(' ')
            )

            def tito_lines = tito_output.tokenize('\n')
            def task_line = tito_lines.find{ it =~ /^Created Task: / }
            def task_matcher = task_line =~ /^Created Task:\s+([0-9]+)/
            brew_task_id = task_matcher[0][1]
            brew_task_url = brew_task_url_prefix + brew_task_id
            pipeline.echo "${package_name} rpm brew task: ${brew_task_id}"

            try {
                pipeline.sh "REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt brew watch-task ${brew_task_id}"
            } catch (build_err) {
                pipeline.echo "Error in ${package_name} build task: ${brew_task_url}"
                throw build_err
            }
        }

        return brew_task_id
    }
}
