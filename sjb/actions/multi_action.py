from __future__ import print_function, unicode_literals, absolute_import

from .interface import Action

class MultiAction(Action):
    """
    A MultiAction action wraps many actions.
    """

    def __init__(self, children):
        self.children = children

    def generate_parameters(self):
        parameters = []
        for child in self.children:
            parameters.extend(child.generate_parameters())

        return parameters

    def generate_build_steps(self):
        build_steps = []
        for child in self.children:
            build_steps.extend(child.generate_build_steps())

        return build_steps

    def generate_post_build_steps(self):
        post_build_steps = []
        for child in self.children:
            post_build_steps.extend(child.generate_post_build_steps())

        return post_build_steps