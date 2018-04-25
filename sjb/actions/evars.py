from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from .interface import Action
from .script import ScriptAction

_EVARS_ACTION_TEMPLATE = Template("""sudo chmod o+rw /etc/environment
echo 'EXTRA_EVARS="{{ evars }}"' >> /etc/environment""")


class EvarsAction(Action):
    """
    A EvarsAction generates a build step that
    records extra -e vars for the Ansible install
    """

    def __init__(self, evars, output_format):
        self.evars = evars
        self.output_format = output_format

    def generate_parameters(self):
        return []

    def generate_build_steps(self):
        return ScriptAction(
            repository=None,
            title="RECORD EXTRA EVARS",
            script=_EVARS_ACTION_TEMPLATE.render(evars=self.evars),
            timeout=None,
            output_format = self.output_format
        ).generate_build_steps()
