from __future__ import absolute_import, print_function, unicode_literals

from .interface import Action
from .named_shell_task import render_task

_DEPROVISION_TITLE = "DEPROVISION CLOUD RESOURCES"
_DEPROVISION_ACTION = "oct deprovision"


class DeprovisionAction(Action):
    """
    A DeprovisionAction generates a post-build
    step that deprovisions the remote host.
    """

    def generate_post_build_steps(self):
        return [render_task(
            title=_DEPROVISION_TITLE,
            command=_DEPROVISION_ACTION,
            output_format=self.output_format
        )]
