from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_FORWARD_PARAMETERS_TITLE = "FORWARD PARAMETERS TO THE REMOTE HOST"
_FORWARD_PARAMETERS_ACTION_TEMPLATE = Template("""ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel sudo chmod o+rw /etc/environment
{% for parameter in parameters %}ssh -F ${WORKSPACE}/.config/origin-ci-tool/inventory/.ssh_config openshiftdevel "echo '{{ parameter }}=${{ '{' }}{{ parameter }}:-{{ '}' }}' >> /etc/environment"
{% endfor %}""")


class ForwardParametersAction(Action):
    """
    A ForwardParametersAction generates a build step
    in which the given parameters are forwarded from
    the controller host to the remote host.
    """

    def __init__(self, parameters):
        self.parameters = parameters

    def generate_build_steps(self):
        return [render_task(
            title=_FORWARD_PARAMETERS_TITLE,
            command=_FORWARD_PARAMETERS_ACTION_TEMPLATE.render(parameters=self.parameters),
            output_format=self.output_format
        )]
