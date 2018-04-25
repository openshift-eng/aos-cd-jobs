from __future__ import absolute_import, print_function, unicode_literals

from jinja2 import Template

from actions.named_shell_task import render_task
from .interface import Action

_TARGET_BRANCH_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>{{ repository | replace('-', '_') | upper }}_TARGET_BRANCH</name>
          <description>The branch in the &lt;a href=&quot;https://github.com/openshift/{{ repository }}&quot;&gt;{{ repository }}&lt;/a&gt; repository to test against.</description>
          <defaultValue>master</defaultValue>
        </hudson.model.StringParameterDefinition>""")

_POST_PULL_REFS_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>PULL_REFS</name>
          <description>Used by prow. If this is not a pull request, it should at least contain the branch:hash of the HEAD being tested.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_POST_BUILD_ID_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>buildId</name>
          <description>The ID that prow sets on a Jenkins job in order to correlate it with a ProwJob.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_POST_BUILD_ID_NEW_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>BUILD_ID</name>
          <description>The ID that prow sets on a Jenkins job in order to correlate it with a ProwJob.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_PROW_JOB_ID_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>PROW_JOB_ID</name>
          <description>The ID that prow sets on a Jenkins job in order to correlate it with a ProwJob.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_REPO_OWNER_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>REPO_OWNER</name>
          <description>GitHub org that triggered the job.</description>
          <defaultValue></defaultValue>
        </hudson.model.StringParameterDefinition>""")

_REPO_NAME_PARAMETER_TEMPLATE = Template("""        <hudson.model.StringParameterDefinition>
          <name>REPO_NAME</name>
          <description>GitHub repo that triggered the job.</description>
          <defaultValue></defaultValue>
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
        return [
            _TARGET_BRANCH_PARAMETER_TEMPLATE.render(repository=self.repository),
            _POST_PULL_REFS_PARAMETER_TEMPLATE.render(),
            _POST_BUILD_ID_PARAMETER_TEMPLATE.render(),
            _POST_BUILD_ID_NEW_PARAMETER_TEMPLATE.render(),
            _PROW_JOB_ID_PARAMETER_TEMPLATE.render(),
            _REPO_OWNER_PARAMETER_TEMPLATE.render(),
            _REPO_NAME_PARAMETER_TEMPLATE.render(),
        ]

    def generate_build_steps(self):
        return [render_task(
            title=_SYNC_TITLE_TEMPLATE.render(repository=self.repository),
            command=_SYNC_ACTION_TEMPLATE.render(repository=self.repository, dependency_repository=self.dependency_repository),
            output_format=self.output_format
        )]

    def description(self):
        return _SYNC_DESCRIPTION_TEMPLATE.render(repository=self.repository, dependency_repository=self.dependency_repository)
