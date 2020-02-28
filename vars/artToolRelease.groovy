def call(String gitUrl=None, String gitBranch="master", pypiCredName=None) {
  pipeline {
    options {
      timestamps()
    }
    agent {
      kubernetes {
        cloud "openshift"
        label "jenkins-agent-${env.JOB_BASE_NAME}-${env.BUILD_NUMBER}"
        //serviceAccount "jenkins"
        defaultContainer 'jnlp'
        yaml """
        apiVersion: v1
        kind: Pod
        metadata:
          labels:
            app: "jenkins"
        spec:
            containers:
            - name: jnlp
              image: "docker-registry.default.svc:5000/art-jenkins/art-jenkins-slave:latest"
              imagePullPolicy: Always
              tty: true
              resources:
                requests:
                  memory: 378Mi
                  cpu: 200m
                limits:
                  memory: 768Mi
                  cpu: 500m
        """
      }
    }
    stages {
      stage("Checkout") {
        steps {
          script {
            def scmVars = checkout(
              scm: [$class: 'GitSCM',
                branches: [[name: gitBranch]],
                userRemoteConfigs: [
                  [
                    name: 'origin',
                    url: gitUrl,
                    refspec: '+refs/heads/*:refs/remotes/origin/* +refs/tags/*:refs/remotes/origin/tags/* +refs/pull/*/head:refs/remotes/origin/pull/*/head',
                  ],
                ],
                extensions: [[$class: 'CleanBeforeCheckout']],
              ],
              poll: false,
              changelog: false,
            )
            env.GIT_COMMIT = scmVars.GIT_COMMIT
            // setting build display name
            def prefix = 'origin/'
            def branch = scmVars.GIT_BRANCH.startsWith(prefix) ? scmVars.GIT_BRANCH.substring(prefix.size())
              : scmVars.GIT_BRANCH // origin/pull/1234/head -> pull/1234/head, origin/master -> master
            env.GIT_BRANCH = branch
            echo "Build on branch=${env.GIT_BRANCH}, commit=${env.GIT_COMMIT}"
            currentBuild.displayName = "${env.GIT_BRANCH}: ${env.GIT_COMMIT.substring(0, 7)}"
          }
        }
      }
      // stage("Test") {
      //   steps {
      //     echo "Testing release..."
      //     sh "tox"
      //   }
      // }
      stage("Build") {
        steps {
          echo "Generating distribution archives..."
          sh "python3 setup.py sdist bdist_wheel"
        }
      }
      stage("Publish to PyPI") {
        when {
          expression { return !!pypiCredName }
        }
        steps {
          withCredentials([usernamePassword(
            credentialsId: pypiCredName,
            usernameVariable: "TWINE_USERNAME",
            passwordVariable: "TWINE_PASSWORD"
          )]) {
            sh "python3 -m twine upload dist/*"
          }
        }
      }
    }
  }
}
