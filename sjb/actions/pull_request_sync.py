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

_PR_SYNC_TITLE_TEMPLATE = Template("SYNC {{ repository | upper }} PULL REQUEST ${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}")
_PR_SYNC_ACTION_TEMPLATE = Template("""oct sync remote {{ repository }} --refspec "pull/${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}/head" --branch "pull-${{ '{' }}{{ repository | replace('-', '_') | upper }}_PULL_ID}" --merge-into "${{ '{' }}{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH}" """)

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
        self.parent_sync = SyncAction(repository)

    def generate_parameters(self):
        return self.parent_sync.generate_parameters() + [
            _PR_ID_PARAMETER_TEMPLATE.render(repository=self.repository)
        ]

    def generate_build_steps(self):
        return self.parent_sync.generate_build_steps() + [
            render_task(
                title=_PR_SYNC_TITLE_TEMPLATE.render(repository=self.repository),
                command=_PR_SYNC_ACTION_TEMPLATE.render(repository=self.repository)
            )
        ]

    def description(self):
        return _PR_SYNC_DESCRIPTION_TEMPLATE.render(repository=self.repository)
