from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from .forward_parameter import ForwardParametersAction
from .interface import Action
from .named_shell_task import render_task
from .script import ScriptAction

_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>{{ name }}</name>
          <description>{{ description }}</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_CLONEREFS_ACTION_TEMPLATE = Template("""if [[ "$( jq --compact-output ".buildid" <<<"${JOB_SPEC}" )" =~ ^\"[0-9]+\"$ ]]; then
  echo "Keeping BUILD_ID"
else
  echo "Using BUILD_NUMBER"
  JOB_SPEC="$( jq --compact-output '.buildid |= "'"${BUILD_NUMBER}"'"' <<<"${JOB_SPEC}" )"
fi
for image in 'registry.svc.ci.openshift.org/ci/clonerefs:latest' 'registry.svc.ci.openshift.org/ci/initupload:latest'; do
    for (( i = 0; i < 5; i++ )); do
        if docker pull "${image}"; then
            break
        fi
    done
done
clonerefs_args=${CLONEREFS_ARGS:-{% for repo in repos %}--repo={{repo}} {% endfor %}}
docker run -e JOB_SPEC="${JOB_SPEC}" -v /data:/data:z registry.svc.ci.openshift.org/ci/clonerefs:latest --src-root=/data --log=/data/clone.json ${clonerefs_args}
docker run -e JOB_SPEC="${JOB_SPEC}" -v /data:/data:z registry.svc.ci.openshift.org/ci/initupload:latest --clone-log=/data/clone.json --dry-run=false --gcs-bucket=origin-ci-test --gcs-credentials-file=/data/credentials.json --path-strategy=single --default-org=openshift --default-repo=origin
sudo chmod -R a+rwX /data
sudo chown -R origin:origin-git /data
""")


class ClonerefsAction(Action):
    """
    A ClonerefsAction generates a build step that
    synchronizes repositories on the remote host
    """

    def __init__(self, repos):
        self.repos = repos

    def generate_parameters(self):
        return [
            _PARAMETER_TEMPLATE.render(name='JOB_SPEC', decsription='JSON form of job specification.'),
            _PARAMETER_TEMPLATE.render(name='buildId', decsription='Unique build number for each run.'),
            _PARAMETER_TEMPLATE.render(name='BUILD_ID', decsription='Unique build number for each run.'),
            _PARAMETER_TEMPLATE.render(name='REPO_OWNER', decsription='GitHub org that triggered the job.'),
            _PARAMETER_TEMPLATE.render(name='REPO_NAME', decsription='GitHub repo that triggered the job.'),
            _PARAMETER_TEMPLATE.render(name='PULL_BASE_REF', decsription='Ref name of the base branch.'),
            _PARAMETER_TEMPLATE.render(name='PULL_BASE_SHA', decsription='Git SHA of the base branch.'),
            _PARAMETER_TEMPLATE.render(name='PULL_REFS', decsription='All refs to test.'),
            _PARAMETER_TEMPLATE.render(name='PULL_NUMBER', decsription='Pull request number.'),
            _PARAMETER_TEMPLATE.render(name='PULL_PULL_SHA', decsription='Pull request head SHA.'),
            _PARAMETER_TEMPLATE.render(name='CLONEREFS_ARGS', decsription='Pull request head SHA.'),
        ]

    def generate_build_steps(self):
        return [render_task(
            title="FORWARD GCS CREDENTIALS TO REMOTE HOST",
            command="""for (( i = 0; i < 10; i++ )); do
    if scp -F ./.config/origin-ci-tool/inventory/.ssh_config /var/lib/jenkins/.config/gcloud/gcs-publisher-credentials.json openshiftdevel:/data/credentials.json; then
        break
    fi
done"""
        )] + ForwardParametersAction(
            parameters=['JOB_SPEC', 'buildId', 'BUILD_ID', 'REPO_OWNER', 'REPO_NAME', 'PULL_BASE_REF', 'PULL_BASE_SHA',
                        'PULL_REFS', 'PULL_NUMBER', 'PULL_PULL_SHA', 'JOB_SPEC', 'BUILD_NUMBER', 'CLONEREFS_ARGS']
        ).generate_build_steps() + ScriptAction(
            repository=None,
            title="SYNC REPOSITORIES",
            script=_CLONEREFS_ACTION_TEMPLATE.render(repos=self.repos),
            timeout=None
        ).generate_build_steps()
