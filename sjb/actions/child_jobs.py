from __future__ import print_function, unicode_literals, absolute_import

from jinja2 import Template

from .interface import Action

_CHILD_JOB_ACTION_TEMPLATE = Template("""    <com.tikal.jenkins.plugins.multijob.MultiJobBuilder>
      <phaseName>Test Phase</phaseName>
      <phaseJobs>
{%- for child_job in child_jobs %}
        <com.tikal.jenkins.plugins.multijob.PhaseJobsConfig>
          <jobName>{{ child_job }}</jobName>
          <currParams>true</currParams>
          <exposedSCM>false</exposedSCM>
          <disableJob>false</disableJob>
          <parsingRulesPath></parsingRulesPath>
          <maxRetries>0</maxRetries>
          <enableRetryStrategy>false</enableRetryStrategy>
          <enableCondition>false</enableCondition>
          <abortAllJob>false</abortAllJob>
          <condition></condition>
          <configs class="empty-list"/>
          <killPhaseOnJobResultCondition>NEVER</killPhaseOnJobResultCondition>
          <buildOnlyIfSCMChanges>false</buildOnlyIfSCMChanges>
          <applyConditionOnlyIfNoSCMChanges>false</applyConditionOnlyIfNoSCMChanges>
        </com.tikal.jenkins.plugins.multijob.PhaseJobsConfig>
{%- endfor %}
      </phaseJobs>
      <continuationCondition>ALWAYS</continuationCondition>
    </com.tikal.jenkins.plugins.multijob.MultiJobBuilder>
{%- for child_job in child_jobs %}
    <hudson.plugins.copyartifact.CopyArtifact plugin="copyartifact@1.38">
      <project>{{ child_job }}</project>
      <filter>**</filter>
      <target>{{ child_job }}/</target>
      <excludes></excludes>
      <selector class="hudson.plugins.copyartifact.SpecificBuildSelector">
        <buildNumber>${{ '{' }}{{ child_job | replace('-','_') | upper }}_BUILD_NUMBER}</buildNumber>
      </selector>
      <optional>true</optional>
      <doNotFingerprintArtifacts>true</doNotFingerprintArtifacts>
    </hudson.plugins.copyartifact.CopyArtifact>
{%- endfor %}
    <hudson.tasks.Shell>
      <command># record the log from the downstream job here for FCM parsing
{%- for child_job in child_jobs %}
cat /var/lib/jenkins/jobs/{{ child_job }}/builds/${{ '{' }}{{ child_job | replace('-','_') | upper }}_BUILD_NUMBER}/log
{%- endfor %}
      </command>
    </hudson.tasks.Shell>""")

class ChildJobAction(Action):
    """
    A ChildJobAction runs child jobs and grabs
    their jUnit artifacts and logs into the
    parent.
    """

    def __init__(self, children):
        self.children = children

    def generate_build_steps(self):
        return [_CHILD_JOB_ACTION_TEMPLATE.render(child_jobs=self.children)]