from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_PROVISION_TITLE = "PROVISION CLOUD RESOURCES"
_PROVISION_ACTION_TEMPLATE = Template("""oct provision remote all-in-one --os "{{ os }}" --stage "{{ stage }}" --provider "{{ provider }}" --discrete-ssh-config --name "${JOB_NAME}_${BUILD_NUMBER}" """)


class ProvisionAction(Action):
    """
    A ProvisionAction generates a build step
    that provisions the remote host.
    """

    def __init__(self, os, stage, provider):
        self.os = os
        self.stage = stage
        self.provider = provider

    def generate_build_steps(self):
        return [render_task(
            title=_PROVISION_TITLE,
            command=_PROVISION_ACTION_TEMPLATE.render(
                os=self.os,
                stage=self.stage,
                provider=self.provider,
            ),
            output_format=self.output_format
        )]
