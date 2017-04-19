from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from .interface import Action

_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>{{ name | escape }}</name>
          <description>{{ description | escape }}</description>
          <defaultValue>{{ default_value | escape }}</defaultValue>
        </hudson.model.StringParameterDefinition>""")

class ParameterAction(Action):
    """
    A ParameterAction adds a parameter to the job.
    """
    def __init__(self, name, description, default_value=''):
        self.name = name
        self.description = description
        self.default_value = default_value

    def generate_parameters(self):
        return [_PARAMETER_TEMPLATE.render(name=self.name, description=self.description, default_value=self.default_value)]