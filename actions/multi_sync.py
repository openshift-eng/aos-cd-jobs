from __future__ import print_function, unicode_literals, absolute_import

from jinja2 import Template

from .interface import Action
from .multi_action import MultiAction

_SYNC_DESCRIPTION_TEMPLATE = Template("""    <hudson.plugins.descriptionsetter.DescriptionSetterBuilder plugin="description-setter@1.10">
      <regexp></regexp>
      <description>{{ description | escape }}</description>
    </hudson.plugins.descriptionsetter.DescriptionSetterBuilder>""")


class MultiSyncAction(Action):
    """
    A MultiSync action wraps many sync actions
    in order to generate a coherent description
    setting build step.
    """

    def __init__(self, children):
        self.multi = MultiAction(children)
        self.children = children

    def generate_parameters(self):
        return self.multi.generate_parameters()

    def generate_build_steps(self):
        return self.description() + self.multi.generate_build_steps()

    def generate_post_build_steps(self):
        return self.multi.generate_post_build_steps()

    def description(self):
        description_lines = ["<div>"]
        child_descriptions="{}".format("<br/>\n".join([child.description() for child in self.children]))
        description_lines.append(child_descriptions)
        description_lines.append("</div>")

        return [_SYNC_DESCRIPTION_TEMPLATE.render(description="\n".join(description_lines))]
