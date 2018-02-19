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

_SYNC_ACTION_TEMPLATE = Template("""docker run -e JOB_SPEC="${JOB_SPEC}" -v /data:/data:z registry.svc.ci.openshift.org/ci/clonerefs:latest --src-root /data --log /data/clone.json {% for repo in repos %}--repo {{repo}}{% endfor %}
docker run -e JOB_SPEC="${JOB_SPEC}" -v /data:/data:z registry.svc.ci.openshift.org/ci/initupload:latest --log /data/clone.json --dry-run false --gcs-bucket origin-ci-test --gcs-credentials-file /data/credentials.json""")


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
        ]

    def generate_build_steps(self):
        return [render_task(
            title="FORWARD GCS CREDENTIALS TO REMOTE HOST",
            command="scp -F ./.config/origin-ci-tool/inventory/.ssh_config /var/lib/jenkins/.config/gcloud/gcs-publisher-credentials.json openshiftdevel:/data/credentials.json"
        )] + ForwardParametersAction(
            parameters=['JOB_SPEC', 'buildId', 'BUILD_ID', 'REPO_OWNER', 'REPO_NAME', 'PULL_BASE_REF', 'PULL_BASE_SHA',
                        'PULL_REFS', 'PULL_NUMBER', 'PULL_PULL_SHA', 'JOB_SPEC']
        ).generate_build_steps() + ScriptAction(
            title="SYNC REPOSITORIES",
            script=_SYNC_ACTION_TEMPLATE.render(repos=self.repos)
        ).generate_build_steps()
