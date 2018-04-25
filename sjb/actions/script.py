from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_SCRIPT_TITLE = "EXECUTE A SCRIPT ON THE REMOTE HOST"
_SCRIPT_ACTION_TEMPLATE = Template("""script="$( mktemp )"
cat <<SCRIPT >"${script}"
#!/bin/bash
set -o errexit -o nounset -o pipefail -o xtrace
{%- if repository %}
cd "\${GOPATH}/src/github.com/openshift/{{ repository }}"
{%- else %}
cd "\${HOME}"
{%- endif %}
{{ command | replace("$", "\$") }}
SCRIPT
chmod +x "${script}"
scp -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config "${script}" openshiftdevel:"${script}"
ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config -t openshiftdevel "bash -l -c \\"timeout {{ timeout }} ${script}\\"" """)


class ScriptAction(Action):
    """
    A ScriptAction generates a build step in which
    the given script is run on the remote host. If
    a repository is given, the script is run with
    the repository as the working directory.
    """

    def __init__(self, repository, script, title, timeout, output_format):
        self.repository = repository
        self.script = script
        if title == None:
            title = _SCRIPT_TITLE
        if timeout == None:
            timeout = 14400
        self.title = title
        self.timeout = timeout
        self.output_format = output_format

    def generate_build_steps(self):
        return [render_task(
            title=self.title,
            command=_SCRIPT_ACTION_TEMPLATE.render(
                repository=self.repository,
                command=self.script,
                timeout=self.timeout
            ),
            output_format=self.output_format
        )]
