from __future__ import absolute_import, print_function, unicode_literals

from .interface import Action

class PostAction(Action):
    """
    A PostAction generates a post-build step in which
    the given action is executed as a post-build step.
    """

    def __init__(self, action):
        self.action = action

    def generate_post_build_steps(self):
        return self.action.generate_build_steps()
