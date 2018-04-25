from __future__ import print_function, unicode_literals, absolute_import

from jinja2 import Template

_PREAMBLE_TEMPLATE = Template("""SCRIPT_START_TIME="$( date +%s )"
export SCRIPT_START_TIME
echo "########## STARTING STAGE: {{ title | upper }} ##########"
trap 'export status=FAILURE' ERR
trap 'set +o xtrace; SCRIPT_END_TIME="$( date +%s )"; ELAPSED_TIME="$(( SCRIPT_END_TIME - SCRIPT_START_TIME ))"; echo "########## FINISHED STAGE: ${status:-SUCCESS}: {{ title | upper }} [$( printf "%02dh %02dm %02ds" "$(( ELAPSED_TIME/3600 ))" "$(( (ELAPSED_TIME%3600)/60 ))" "$(( ELAPSED_TIME%60 ))" )] ##########"' EXIT
set -o errexit -o nounset -o pipefail -o xtrace
if [[ -s "${WORKSPACE}/activate" ]]; then source "${WORKSPACE}/activate"; fi""")

_NAMED_SHELL_TASK_SH_TEMPLATE = Template("""{{ preamble }}
{{ command }}
""")

_NAMED_SHELL_TASK_XML_TEMPLATE = Template("""        <hudson.tasks.Shell>
          <command>#!/bin/bash
{{ shell_command | escape }}</command>
        </hudson.tasks.Shell>""")

def render_task(title, command, output_format):
    shell_command = _NAMED_SHELL_TASK_SH_TEMPLATE.render(
        preamble=" && ".join(_PREAMBLE_TEMPLATE.render(title=title).splitlines()),
        command=command
    )
    if output_format == "sh":
        return shell_command
    else:
        return _NAMED_SHELL_TASK_XML_TEMPLATE.render(
            shell_command=shell_command
        )
