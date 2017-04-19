from __future__ import absolute_import, print_function, unicode_literals

from .interface import Action
from .host_script import HostScriptAction

class PostHostScriptAction(Action):
    """
    A PostHostScriptAction generates a post-build step
    in which the given script is run on the controller
    host.
    """

    def __init__(self, script, title):
        self.action = HostScriptAction(script, title)

    def generate_post_build_steps(self):
        return self.action.generate_build_steps()
