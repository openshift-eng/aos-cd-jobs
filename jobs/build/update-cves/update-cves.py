import shutil
from github import Github
import urllib2
import yaml
import json
import os
import sys
import click


github_repo = "openshift/ocp-build-data"
freshmaker_url_prefix = "https://freshmaker.engineering.redhat.com/api/1/builds/?name="
base_images = {"rhel": "rhel-server-container", "ansible-runner": "ansible-runner-container",
               "elasticsearch": "elasticsearch-container", "jboss-openjdk18": "jboss-openjdk18-rhel7-container",
               "nodejs-6": "rh-nodejs6-container"}


def fetch_remote_nvr_from_freshmaker_api(k):
    response = urllib2.urlopen(freshmaker_url_prefix + base_images[k])
    json_data = json.load(response)
    return str(json_data['items'][0]['rebuilt_nvr'])


def replace_version(l_nvr, r_nvr):
    return l_nvr.split(":")[0] + ":" + r_nvr.split("container-")[1]


def version_compare_update(l_nvr, r_nvr):
    lvr = l_nvr.split(":")[1]
    rvr = r_nvr.split("container-")[1]

    lv, lr = lvr.split("-")[0], lvr.split("-")[1]
    rv, rr = rvr.split("-")[0], rvr.split("-")[1]

    if lvr == rvr:
        return False
    if lv > rv:
        return False
    if lv == rv and lr > rr:
        return False

    return True


def local_files_updated(stream_file_path):
    changed = False
    with open(stream_file_path, 'rw') as f:
        doc = yaml.safe_load(f)
        for key, value in doc.items():
            local_nvr = value['image']
            remote_nvr = fetch_remote_nvr_from_freshmaker_api(key)

            if version_compare_update(local_nvr, remote_nvr):
                changed = True
                value['image'] = replace_version(local_nvr, remote_nvr)

    if changed:
        with open(stream_file_path, 'w') as f:
            yaml.dump(doc, f)

    return changed


@click.command()
@click.option("-f", "--filepath", default=None, metavar='NAME', required=True,
              help="The path of stream.yml file on ocp-build-data need to update")
def main(filepath):
    try:
        local_files_updated(filepath)

    except Exception as ex:
        print ex
        sys.exit(1)


if __name__ == '__main__':
    main()

