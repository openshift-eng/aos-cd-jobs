from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_TARGET_BRANCH_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH</name>
          <description>The branch in the &lt;a href=&quot;https://github.com/openshift/{{ repository }}&quot;&gt;{{ repository }}&lt;/a&gt; repository to test against.</description>
          <defaultValue>master</defaultValue>
        </hudson.model.StringParameterDefinition>""")

_SYNC_TITLE_TEMPLATE = Template("SYNC {{ repository | upper }} REPOSITORY")
_SYNC_ACTION_TEMPLATE = Template("""oct sync remote {{ repository }} --branch "${{ '{' }}{{ dependency_repository | replace('-', '_') | upper }}_TARGET_BRANCH}" """)

_SYNC_DESCRIPTION_TEMPLATE = Template("""Using the <a href="https://github.com/openshift/{{ repository }}/tree/${{ '{' }}{{ dependency_repository | replace('-', '_') | upper }}_TARGET_BRANCH}">{{ repository }} ${{ '{' }}{{ dependency_repository | replace('-', '_') | upper }}_TARGET_BRANCH}</a> branch.""")


class SyncAction(Action):
    """
    A SyncAction generates a build step that
    synchronizes a repository on the remote
    host and checkout a matching branch based
    on the dependency repository
    """

    def __init__(self, repository, dependency_repository):
        self.repository = repository
        self.dependency_repository = dependency_repository

    def generate_parameters(self):
        return [_TARGET_BRANCH_PARAMETER_TEMPLATE.render(repository=self.repository)]

    def generate_build_steps(self):
        return [render_task(
            title=_SYNC_TITLE_TEMPLATE.render(repository=self.repository),
            command=_SYNC_ACTION_TEMPLATE.render(repository=self.repository, dependency_repository=self.dependency_repository)
        )]

    def description(self):
        return _SYNC_DESCRIPTION_TEMPLATE.render(repository=self.repository, dependency_repository=self.dependency_repository)
