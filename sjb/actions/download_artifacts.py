from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_DOWNLOAD_ARTIFACTS_TITLE = "DOWNLOAD ARTIFACTS FROM THE REMOTE HOST"
_DOWNLOAD_ARTIFACTS_ACTION_TEMPLATE = Template("""trap 'exit 0' EXIT
ARTIFACT_DIR="$( pwd )/artifacts/gathered"
rm -rf "${ARTIFACT_DIR}"
mkdir -p "${ARTIFACT_DIR}"
{%- for artifact in artifacts %}
if ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel sudo stat {{ artifact }}; then
    ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel sudo chmod -R o+rX {{ artifact }}
    scp -r -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel:{{ artifact }} "${ARTIFACT_DIR}"
fi
{%- endfor %}
tree "${ARTIFACT_DIR}" """)


class DownloadArtifactsAction(Action):
    """
    A DownloadArtifactsAction generates a post-build
    step which downloads the given files from the
    remote host.
    """

    def __init__(self, artifacts):
        self.artifacts = artifacts

    def generate_post_build_steps(self):
        return [render_task(
            title=_DOWNLOAD_ARTIFACTS_TITLE,
            command=_DOWNLOAD_ARTIFACTS_ACTION_TEMPLATE.render(artifacts=self.artifacts),
            output_format=self.output_format
        )]
