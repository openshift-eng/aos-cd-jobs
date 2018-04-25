from __future__ import absolute_import, print_function, unicode_literals

from actions.named_shell_task import render_task
from .interface import Action

_HOST_SCRIPT_TITLE = "EXECUTE A SCRIPT ON THE CONTROLLER HOST"


class HostScriptAction(Action):
    """
    A HostScriptAction generates a build step in which
    the given script is run on the controller host.
    """

    def __init__(self, script, title):
        self.script = script
        if title == None:
            title = _HOST_SCRIPT_TITLE
        self.title = title

    def generate_build_steps(self):
        return [render_task(
            title=self.title,
            command=self.script,
            output_format=self.output_format
        )]
