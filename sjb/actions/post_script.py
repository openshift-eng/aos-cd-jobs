from __future__ import absolute_import, print_function, unicode_literals

from .interface import Action
from .script import ScriptAction

class PostScriptAction(Action):
    """
    A PostScriptAction generates a post-build step
    in which the given script is run on the remote
    host. If a repository is given, the script is
    run with the repository as the working directory.
    """

    def __init__(self, repository, script, title):
        self.action = ScriptAction(repository, script, title)

    def generate_post_build_steps(self):
        return self.action.generate_build_steps()
