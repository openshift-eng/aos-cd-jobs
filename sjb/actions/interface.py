from __future__ import print_function, unicode_literals, absolute_import

class Action(object):
    output_format = "xml"

    def generate_parameters(self):
        return []

    def generate_build_steps(self):
        return []

    def generate_post_build_steps(self):
        return []
