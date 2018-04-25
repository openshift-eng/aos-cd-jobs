#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

{%- for build_step in build_steps %}
{{ build_step }}
{%- endfor %}
