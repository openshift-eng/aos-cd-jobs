#!/usr/bin/env python

import sys
from xml.dom.minidom import parse

from jinja2 import Environment, FileSystemLoader
from os.path import abspath, basename, dirname, join, splitext
from yaml import dump, load

from actions.child_jobs import ChildJobAction
from actions.deprovision import DeprovisionAction
from actions.download_artifacts import DownloadArtifactsAction
from actions.forward_parameter import ForwardParametersAction
from actions.generate_artifacts import GenerateArtifactsAction
from actions.host_script import HostScriptAction
from actions.multi_action import MultiAction
from actions.multi_sync import MultiSyncAction
from actions.oct_install import OCTInstallAction
from actions.parameter import ParameterAction
from actions.post_host_script import PostHostScriptAction
from actions.post_script import PostScriptAction
from actions.provision import ProvisionAction
from actions.pull_request_sync import PullRequestSyncAction
from actions.repo_sync import SyncAction
from actions.script import ScriptAction
from actions.systemd_journal import SystemdJournalAction

config_base_dir = abspath(join(dirname(__file__), 'config'))


def load_configuration(config_path):
    """
    Load a job configuration by adding the overrides and
    extensions to a parent configuration, if applicable,
    else loading in explicit wants from this config.
    """
    with open(config_path) as config_file:
        job_config = load(config_file)

    if "parent" in job_config:
        parent_config_path = job_config.get("parent")
        parent_config = load_configuration(join(config_base_dir, parent_config_path))

        for entry, override in job_config.get("overrides", {}).items():
            parent_config[entry] = override

        for entry, extension in job_config.get("extensions", {}).items():
            if isinstance(parent_config[entry], list):
                parent_config[entry].extend(extension)
            elif isinstance(parent_config[entry], dict):
                parent_config[entry].update(extension)
            else:
                print("Unsupported config entry {} with type: {}".format(entry, type(entry)))
                sys.exit(1)

        return parent_config
    else:
        return job_config


if len(sys.argv) != 3:
    print("USAGE: {} CONFIG JOB_TYPE".format(sys.argv[0]))
    sys.exit(2)
elif sys.argv[2] not in ["suite", "test"]:
    print("Job type must be one of `suite` or `test`.")
    sys.exit(2)

job_config_path = sys.argv[1]
job_type = sys.argv[2]
job_name = splitext(basename(job_config_path))[0]
print("[INFO] Generating configuration for {} job {}".format(job_type, job_name))
job_config = load_configuration(job_config_path)
print("[INFO] Using configuration:\n{}".format(
    dump(job_config, default_flow_style=False, explicit_start=True))
)

actions = []

if job_type == "test":
    for parameter in job_config.get("parameters", []):
        actions.append(ParameterAction(
            name=parameter.get("name"),
            description=parameter.get("description"),
            default_value=parameter.get("default_value", ""),
        ))

    # all jobs will install the tool first
    actions.append(OCTInstallAction())

    # next, all jobs will provision a remote VM
    actions.append(ProvisionAction(
        os=job_config["provision"]["os"],
        stage=job_config["provision"]["stage"],
        provider=job_config["provision"]["provider"],
    ))

    # next, repositories will be synced to the remote VM
    sync_actions = []
    for repository in job_config.get("sync_repos", []):
        if repository.get("type", None) == "pull_request":
            sync_actions.append(PullRequestSyncAction(repository["name"]))
        else:
            sync_actions.append(SyncAction(repository["name"]))

    if len(sync_actions) > 0:
        actions.append(MultiSyncAction(sync_actions))

    # now, the job can define actions to take
    for action in job_config.get("actions", []):
        if action["type"] == "script":
            actions.append(ScriptAction(action.get("repository", None), action["script"], action.get("title", None)))
        elif action["type"] == "host_script":
            actions.append(HostScriptAction(action["script"], action.get("title", None)))
        elif action["type"] == "forward_parameters":
            actions.append(ForwardParametersAction(action.get("parameters", [])))

    # next, the job needs to retrieve artifacts
    if "artifacts" in job_config:
        actions.append(DownloadArtifactsAction(job_config["artifacts"]))

    # some artifacts may not exist on the remote filesystem
    # but will need to be generated
    if "generated_artifacts" in job_config:
        actions.append(GenerateArtifactsAction(job_config["generated_artifacts"]))

    if "system_journals" in job_config:
        actions.append(SystemdJournalAction(job_config["system_journals"]))

    for post_action in job_config.get("post_actions", []):
        if post_action["type"] == "script":
            actions.append(PostScriptAction(post_action.get("repository", None), post_action["script"], post_action.get("title", None)))
        elif post_action["type"] == "host_script":
            actions.append(PostHostScriptAction(post_action["script"], post_action.get("title", None)))

    # finally, the job will deprovision cloud resources
    actions.append(DeprovisionAction())
elif job_type == "suite":
    registered_names = []
    for child in job_config["children"]:
        child_config_path = abspath(join(dirname(__file__), "generated", "{}.xml".format(child)))
        print("[INFO] Checking child {} for parameters".format(child))
        child_config = parse(child_config_path)

        for parameter_definition in child_config.getElementsByTagName("hudson.model.StringParameterDefinition"):
            parameter_name = parameter_definition.getElementsByTagName("name")[0].childNodes[0].nodeValue
            parameter_description = parameter_definition.getElementsByTagName("description")[0].childNodes[0].nodeValue
            if len(parameter_definition.getElementsByTagName("defaultValue")[0].childNodes) != 0:
                parameter_default_value = parameter_definition.getElementsByTagName("defaultValue")[0].childNodes[0].nodeValue
            else:
                parameter_default_value = ""

            if parameter_name in registered_names:
                continue

            actions.append(ParameterAction(
                name=parameter_name,
                description=parameter_description,
                default_value=parameter_default_value,
            ))
            registered_names.append(parameter_name)

    print("[INFO] Added the following parameters for child jobs:\n{}".format(",e ".join(registered_names)))
    actions.append(ChildJobAction(job_config["children"]))

generator = MultiAction(actions)

template_dir = abspath(join(dirname(__file__), 'templates'))
env = Environment(loader=FileSystemLoader(template_dir))

action = None
target_repo = None
if "merge" in job_config:
    action = "merge"
    target_repo = job_config["merge"]
if "test" in job_config:
    action = "test"
    target_repo = job_config["test"]

if action != None:
    print("[INFO] Marking this as a {} job for the {} repo".format(action, target_repo))

output_path = abspath(join(dirname(__file__), "generated", "{}.xml".format(job_name)))
with open(output_path, "w") as output_file:
    output_file.write(env.get_template('test_case.xml').render(
        parameters=generator.generate_parameters(),
        build_steps=generator.generate_build_steps(),
        post_build_steps=generator.generate_post_build_steps(),
        action=action,
        target_repo=target_repo,
        timer=job_config.get("timer", None),
        email=job_config.get("email", None)
    ))
print("[INFO] Wrote job definition to {}".format(output_path))
