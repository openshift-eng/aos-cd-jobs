from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_FETCH_SYSTEMD_JOURNAL_TITLE = "FETCH SYSTEMD JOURNALS FROM THE REMOTE HOST"
_FETCH_SYSTEMD_JOURNAL_ACTION_TEMPLATE = Template("""trap 'exit 0' EXIT
ARTIFACT_DIR="$( pwd )/artifacts/journals"
rm -rf "${ARTIFACT_DIR}"
mkdir "${ARTIFACT_DIR}"
{%- for unit in units %}
ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel sudo journalctl --unit {{ unit }} --no-pager --all --lines=all >> "${ARTIFACT_DIR}/{{ unit }}"
{%- endfor %}
tree "${ARTIFACT_DIR}" """)


class SystemdJournalAction(Action):
    """
    A SystemdJournalAction generates a post-build
    step which generates the given logfiles from the
    systemd journal on the remote host.
    """

    def __init__(self, units):
        self.units = units

    def generate_post_build_steps(self):
        return [render_task(
            title=_FETCH_SYSTEMD_JOURNAL_TITLE,
            command=_FETCH_SYSTEMD_JOURNAL_ACTION_TEMPLATE.render(units=self.units),
            output_format=self.output_format
        )]
