from __future__ import absolute_import, print_function, unicode_literals

from xml.dom.minidom import parseString

from jinja2 import Template

from .forward_parameter import ForwardParametersAction
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

    def __init__(self, output_format, children):
        self.multi = MultiAction(output_format, children)
        self.children = children
        self.output_format = output_format

    def generate_parameters(self):
        return self.multi.generate_parameters()

    def generate_build_steps(self):
        return self.description() + self.multi.generate_build_steps() + self.generate_parameter_forwarding_step()

    def generate_post_build_steps(self):
        return self.multi.generate_post_build_steps()

    def description(self):
        description_lines = ["<div>"]
        child_descriptions = "{}".format("<br/>\n".join([child.description() for child in self.children]))
        description_lines.append(child_descriptions)
        description_lines.append("</div>")

        return [_SYNC_DESCRIPTION_TEMPLATE.render(description="\n".join(description_lines))]

    def generate_parameter_forwarding_step(self):
        """
        This is a terrible hack to get around the fact that
        we take structured data from the configuration and
        immediately flatten it into XML strings in these
        generators. A proper approach would keep the data
        structured and, perhaps, do the conversion to XML
        parameter definitions later on, so we did not have
        to parse out from XML here. That challenges a basic
        assumption of generators, we can revisit that in the
        future if SJB is still around.
        """
        parameter_names = []
        for parameter in self.generate_parameters():
            parameter_name = (
                parseString(parameter).
                getElementsByTagName("hudson.model.StringParameterDefinition")[0].
                getElementsByTagName("name")[0].
                childNodes[0].nodeValue
            )
            if parameter_name in parameter_names:
                continue
            parameter_names.append(parameter_name)

        return ForwardParametersAction(parameter_names).generate_build_steps()
