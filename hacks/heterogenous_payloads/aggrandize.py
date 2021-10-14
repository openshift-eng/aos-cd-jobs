#!/usr/bin/python3
import click
import subprocess
import json
import yaml
import pathlib
from typing import Dict, Tuple, List


def execute(cmd_list) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return p.returncode, stdout, stderr


@click.command()
@click.option('-a', '--arch', 'arches', multiple=True, default=['amd64', 's390x', 'ppc64le'], help='Architectures to include in manifest list payload')
@click.option('-r', '--release', required=True, help='Release name (e.g. 4.3.13)')
@click.option("--image-stream-file", required=False, default='', help='Imagestream file appropriate for release payload with manifest lists for components')
@click.option("--dry-run", type=bool, is_flag=True, default=False, help="Only print the information that would be assembled into the new release payload")
@click.option("--push", type=bool, is_flag=True, default=False, help="After assembling, actually push newly created manifests")
def run(arches, release, image_stream_file, dry_run, push):

    payload_manifest_list: Dict[str, str] = dict()  # Maps arch name to manifest list pullspec@sha256
    component_manifest_list: Dict[str, Dict[str, str]] = dict()  # Maps component name to Dict[arch]->pullspec@sha256
    for arch in arches:
        brew_arch_name = arch
        if arch == 'amd64':
            brew_arch_name = 'x86_64'
        elif arch == 'arm64':
            brew_arch_name = 'aarch64'

        arch_payload_pullspec = f'quay.io/openshift-release-dev/ocp-release:{release}-{brew_arch_name}'
        rc, stdout, stderr = execute(['oc', 'adm', 'release', 'info', '--output=json', arch_payload_pullspec])

        if rc != 0:
            print(f'Unable to read release payload information for: {arch_payload_pullspec}')
            print(f'Stderr from oc:\n{stderr}')
            exit(1)

        arch_payload_info = json.loads(stdout)
        arch_payload_sha_pullspec = 'quay.io/openshift-release-dev/ocp-release@' + arch_payload_info['digest']
        payload_manifest_list[arch] = arch_payload_sha_pullspec
        tags = arch_payload_info['references']['spec']['tags']
        for component in tags:
            component_name = component['name']
            component_sha_pullspec = component['from']['name']
            if component_name not in component_manifest_list:
                component_manifest_list[component_name] = dict()
            component_manifest_list[component_name][arch] = component_sha_pullspec

    print('Items to be included in release payload manifest list:')
    print(yaml.safe_dump(payload_manifest_list))
    print('\nComponents to be included in component manifest list:')
    print(yaml.safe_dump(component_manifest_list))
    print('')

    if dry_run:
        print('Exiting because of --dry-run')
        exit(0)

    safe_prefix = f'jupierce-aggrandize-py-{release}'
    is_tags = []
    imagestream_obj = {
        'apiVersion': 'image.openshift.io/v1',
        'kind': 'ImageStream',
        'metadata': {
            'name': safe_prefix,
            'namespace': 'ocp',
        },
        'spec': {
            'tags': is_tags
        }
    }

    if not image_stream_file:
        for component_name in component_manifest_list:
            ml_name = f'quay.io/openshift-release-dev/ocp-v4.0-art-dev:{safe_prefix}-{component_name}'
            print(f'\nCreating component manifest list: {ml_name}')
            execute(['podman', 'manifest', 'rm', ml_name])  # In case this has been run before; we don't care it works
            rc, stdout, stderr = execute(['podman', 'manifest', 'create', ml_name])
            print(stdout)
            if rc != 0:
                print(f'Unable to create manifest list {ml_name}: {stderr}')
                exit(1)

            for arch in component_manifest_list[component_name]:
                pullspec = component_manifest_list[component_name][arch]
                print(f'Adding {pullspec} to {ml_name}...')
                rc, stdout, stderr = execute(['podman', 'manifest', 'add', ml_name, f'docker://{pullspec}'])
                if rc != 0:
                    print(f'Unable to add {pullspec} to manifest list {ml_name}: {stderr}')
                    exit(1)
                else:
                    print(f'Success: {stdout}')

            if not push:
                print(f'Skipping push for component manifest list: {ml_name}')
            else:
                digest_path = pathlib.Path(f'/tmp/{release}-{component_name}.digest')
                rc, stdout, stderr = execute(['podman', 'manifest', 'push', ml_name, f'docker://{ml_name}', '--digestfile', str(digest_path)])
                if rc != 0:
                    print(f'Unable to push manifest list for {component_name}:\n {stderr}')
                    exit(1)
                digest = digest_path.read_text()
                digest_path.unlink()
                print(f'Pushed component {component_name} manifest list to digest: {digest}')
                is_tags.append({
                    'from': {
                        'kind': 'DockerImage',
                        'name': f'quay.io/openshift-release-dev/ocp-v4.0-art-dev@{digest}'
                    },
                    'name': component_name,
                })

    if not push:
        print('Final payload manifest cannot be assembled without --push')
        exit(0)

    if not image_stream_file:
        print('The imagestream file that will serve as the basis of all arch specific release payloads')
        yaml.safe_dump(imagestream_obj)
        print('')
        is_path = pathlib.Path(f'/tmp/{safe_prefix}.yaml')
        is_path.write_text(yaml.safe_dump(imagestream_obj))
    else:
        is_path = pathlib.Path(image_stream_file)

    execute(['podman', 'manifest', 'rm', safe_prefix])  # In case this has been generated before, delete it
    rc, _, stderr = execute(['podman', 'manifest', 'create', safe_prefix])
    if rc != 0:
        print(f'Error creating final manifest list: {safe_prefix}: {stderr}')
        exit(1)

    for arch in payload_manifest_list:
        print(f'Building release payload image for: {arch}...')
        # Now we construct a release payload for each arch.
        arch_dest = f'quay.io/openshift-release-dev/ocp-release-nightly:{release}-multi-{arch}'
        rc, stdout, stderr = execute(['/home/jupierce/go/src/github.com/openshift/oc/oc', 'adm', 'release', 'new', '--reference-mode=source', f'--from-image-stream-file={str(is_path)}', f'--to-image-base={component_manifest_list["cluster-version-operator"][arch]}', f'--name={release}-multi', f'--to-image={arch_dest}'])
        if rc != 0:
            print(f'Error creating release payload for {arch}: {stderr}')
            exit(1)

        rc, stdout, stderr = execute(['oc', 'image', 'info', arch_dest, '--output=json'])
        if rc != 0:
            print(f'Error reading release payload digest information for {arch_dest}')
            exit(1)

        arch_payload_info = json.loads(stdout)
        arch_payload_sha_pullspec = 'quay.io/openshift-release-dev/ocp-release-nightly@' + arch_payload_info['digest']

        rc, stdout, stderr = execute(['podman', 'manifest', 'add', safe_prefix, f'docker://{arch_payload_sha_pullspec}'])
        if rc != 0:
            print(f'Unable to add {arch_dest} / {arch_payload_sha_pullspec} to final payload manifest list: {stderr}')
            exit(1)

    final_dest = f'quay.io/openshift-release-dev/ocp-release-nightly:{release}-multi'
    rc, _, stderr = execute(['podman', 'manifest', 'push', safe_prefix, f'docker://{final_dest}'])
    if rc != 0:
        print(f'Error pushing final manifest list: {safe_prefix}: {stderr}')
        exit(1)

    print(f'Final list/list payload pushed: {final_dest}')


if __name__ == '__main__':
    run()
