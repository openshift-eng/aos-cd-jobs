from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_GENERATE_ARTIFACTS_TITLE = "GENERATE ARTIFACTS FROM THE REMOTE HOST"
_GENERATE_ARTIFACTS_ACTION_TEMPLATE = Template("""trap 'exit 0' EXIT
ARTIFACT_DIR="$( pwd )/artifacts/generated"
rm -rf "${ARTIFACT_DIR}"
mkdir "${ARTIFACT_DIR}"
{%- for name, action in artifacts.iteritems() %}
ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel "{{ action }} 2>&1" >> "${ARTIFACT_DIR}/{{ name }}" || true
{%- endfor %}
tree "${ARTIFACT_DIR}" """)


class GenerateArtifactsAction(Action):
    """
    A GenerateArtifactsAction generates a post-build
    step which generates the given files from actions
    taken on the remote host.
    """

    def __init__(self, artifacts):
        # we expect `artifacts` to be a dictionary of
        # artifact name --> generating action
        self.artifacts = artifacts

    def generate_post_build_steps(self):
        return [render_task(
            title=_GENERATE_ARTIFACTS_TITLE,
            command=_GENERATE_ARTIFACTS_ACTION_TEMPLATE.render(artifacts=self.artifacts),
            output_format=self.output_format
        )]
