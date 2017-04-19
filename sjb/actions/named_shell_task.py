from __future__ import print_function, unicode_literals, absolute_import

from jinja2 import Template

_PREAMBLE_TEMPLATE = Template("""echo "########## STARTING STAGE: {{ title | upper }} ##########"
trap 'export status=FAILURE' ERR
trap 'set +o xtrace; echo "########## FINISHED STAGE: ${status:-SUCCESS}: {{ title | upper }} ##########"' EXIT
set -o errexit -o nounset -o pipefail -o xtrace
if [[ -s "${WORKSPACE}/activate" ]]; then source "${WORKSPACE}/activate"; fi""")

_NAMED_SHELL_TASK_TEMPLATE = Template("""        <hudson.tasks.Shell>
          <command>#!/bin/bash
{{ preamble | escape }}
{{ command | escape }}</command>
        </hudson.tasks.Shell>""")

def render_task(title, command):
    return _NAMED_SHELL_TASK_TEMPLATE.render(
        preamble=" && ".join(_PREAMBLE_TEMPLATE.render(title=title).splitlines()),
        command=command
    )