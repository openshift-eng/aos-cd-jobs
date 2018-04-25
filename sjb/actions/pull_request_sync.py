from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action
from .repo_sync import SyncAction

_PR_ID_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>{{ repository | replace('-', '_') | upper }}_PULL_ID</name>
          <description>The pull-request in the &lt;a href=&quot;https://github.com/openshift/{{ repository }}&quot;&gt;{{ repository }}&lt;/a&gt; repository to test.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_PULL_NUMBER_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>PULL_NUMBER</name>
          <description>The pull-request in the &lt;a href=&quot;https://github.com/openshift/{{ repository }}&quot;&gt;{{ repository }}&lt;/a&gt; repository to test. This is compatible with prow.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_PULL_REFS_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>PULL_REFS</name>
          <description>The pull-request(s) in the &lt;a href=&quot;https://github.com/openshift/{{ repository }}&quot;&gt;{{ repository }}&lt;/a&gt; repository to test. This is compatible with prow and can be used for batch testing.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_BUILD_ID_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>buildId</name>
          <description>The ID that prow sets on a Jenkins job in order to correlate it with a ProwJob and bubble statuses up to the correct pull request.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_PROW_JOB_ID_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>PROW_JOB_ID</name>
          <description>The ID that prow sets on a Jenkins job in order to correlate it with a ProwJob.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_PR_SYNC_TITLE_TEMPLATE = Template("SYNC {{ repository | upper }} PULL REQUEST ${{ '{' }}PULL_NUMBER:-}${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID:-}")
_PR_SYNC_ACTION_TEMPLATE = Template("""cat << SCRIPT > unravel-pull-refs.py
#!/usr/bin/env python
from __future__ import print_function
import sys

# PULL_REFS is expected to be in the form of:
#
# base_branch:commit_sha_of_base_branch,pull_request_no:commit_sha_of_pull_request_no,...
#
# For example:
#
# master:97d901d,4:bcb00a1
#
# And for multiple pull requests that have been batched:
#
# master:97d901d,4:bcb00a1,6:ddk2tka
print( "\\n".join([r.split(':')[0] for r in sys.argv[1].split(',')][1:]) )
SCRIPT
chmod +x unravel-pull-refs.py

if [[ -n "${PULL_REFS:-}" ]]; then
  for ref in $(./unravel-pull-refs.py $PULL_REFS); do
      oct sync remote {{ repository }} --refspec "pull/$ref/head" --branch "pull-$ref" --merge-into "${{ '{' }}PULL_REFS%%:*}"
   done
elif [[ -n "${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID:-}" ]]; then
  oct sync remote {{ repository }} --refspec "pull/${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}/head" --branch "pull-${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}" --merge-into "${{ '{' }}{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH}"
else
  echo "[ERROR] Either \$PULL_REFS or ${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID:-} and \${{ repository | replace('-', '_') | upper }}_TARGET_BRANCH must be set"
  exit 1
fi
""")

_PR_SYNC_DESCRIPTION_TEMPLATE = Template(
    """Using PR <a href="https://github.com/openshift/{{ repository }}/pull/${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}">${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}</a> merged into the <a href="https://github.com/openshift/{{ repository }}/tree/${{ '{' }}{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH}">{{ repository }} ${{ '{' }}{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH}</a> branch.""")


class PullRequestSyncAction(Action):
    """
    A PullRequestSyncAction generates a build
    step that synchronizes a repository on the
    remote host by merging a pull request into
    the desired branch.
    """

    def __init__(self, repository):
        self.repository = repository
        self.parent_sync = SyncAction(repository, dependency_repository=repository)

    def generate_parameters(self):
        return self.parent_sync.generate_parameters() + [
            _PR_ID_PARAMETER_TEMPLATE.render(repository=self.repository),
            _PULL_NUMBER_PARAMETER_TEMPLATE.render(repository=self.repository),
            _PULL_REFS_PARAMETER_TEMPLATE.render(repository=self.repository),
            _BUILD_ID_PARAMETER_TEMPLATE.render(),
            _PROW_JOB_ID_PARAMETER_TEMPLATE.render(),
        ]

    def generate_build_steps(self):
        return self.parent_sync.generate_build_steps() + [
            render_task(
                title=_PR_SYNC_TITLE_TEMPLATE.render(repository=self.repository),
                command=_PR_SYNC_ACTION_TEMPLATE.render(repository=self.repository),
                output_format=self.output_format
            )
        ]

    def description(self):
        return _PR_SYNC_DESCRIPTION_TEMPLATE.render(repository=self.repository)
