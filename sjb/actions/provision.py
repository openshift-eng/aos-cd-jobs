from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_PROVISION_TITLE = "PROVISION CLOUD RESOURCES"
_PROVISION_ACTION_TEMPLATE = Template("""{%- if validate %}
oct image_not_ready --os "{{ os }}" --stage "{{ stage }}" --provider "{{ provider }}"
{% endif -%}
{%- if instance_type %}
oct configure aws-defaults master_instance_type {{ instance_type }}
{% endif -%}
oct provision remote all-in-one --os "{{ os }}" --stage "{{ stage }}" --provider "{{ provider }}" --discrete-ssh-config --name "${JOB_NAME}_${BUILD_NUMBER}" {% if validate %}--launch-unready{%- endif -%} """)


class ProvisionAction(Action):
    """
    A ProvisionAction generates a build step
    that provisions the remote host.
    """

    def __init__(self, os, stage, provider, instance_type, validate=False):
        self.os = os
        self.stage = stage
        self.provider = provider
        self.instance_type = instance_type
        if not isinstance(validate, bool):
            raise TypeError("'validate' parameter cannot parse as boolean")
        self.validate = validate

    def generate_build_steps(self):
        return [render_task(
            title=_PROVISION_TITLE,
            command=_PROVISION_ACTION_TEMPLATE.render(
                os=self.os,
                stage=self.stage,
                provider=self.provider,
                instance_type=self.instance_type,
                validate=self.validate,
            ),
            output_format=self.output_format
        )]
