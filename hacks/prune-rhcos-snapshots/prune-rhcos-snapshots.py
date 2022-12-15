#!/usr/bin/env python3
import os

import boto3
import openshift as oc
import json
import yaml
import datetime
import urllib3
import pathlib
import subprocess

# Set to "true" if an AMI is selected for garbage collection
AMI_TAG_KEY_GARBAGE_COLLECT = 'garbage_collect'

# Set to a list of release payloads which may depend on this
# AMI. Mutually exclusive with garbage_collect. This list
# may not be exhaustive due to tag size limitations.
AMI_TAG_KEY_REFERENCED_BY = 'referenced_by'


def create_recycle_bin_rule(client, res_type: str):
    response = client.create_rule(
        RetentionPeriod={
            'RetentionPeriodValue': 60,
            'RetentionPeriodUnit': 'DAYS'
        },
        Tags=[
            {
                'Key': 'Name',
                'Value': f'rhcos-preserve-{res_type}'
            },
        ],
        Description=f'Help protect RHCOS {res_type} from accidental deletion',
        ResourceType=res_type,
    )
    print(f'Created new retention rule: {response["Identifier"]}')


if __name__ == '__main__':

    gopath = pathlib.Path(os.getenv('GOPATH'))
    if not gopath.is_dir():
        print('Set GOPATH env before running')
        exit(1)

    installer_git_path = gopath.joinpath('src/github.com/openshift/installer')
    if not installer_git_path.is_dir():
        print(f'Requires recent clone of github.com/openshift/installer in GOPATH: {str(installer_git_path)}')
        exit(1)

    http = urllib3.PoolManager()

    riu_path = pathlib.Path('rhcos_in_use.yaml')
    rhcos_in_use = dict()
    if riu_path.exists():
        rhcos_in_use = yaml.safe_load(riu_path.read_text())

    arches = ['amd64', 's390x', 'ppc64le', 'arm64']
    for arch in arches:
        rc_url = f'https://{arch}.ocp.releases.ci.openshift.org/graph'
        r = http.request('GET', rc_url)
        if r.status != 200:
            print(f'Error retrieving release controller graph data: {r}')
            exit(1)

        graph_str = r.data.decode('utf-8')
        graph = json.loads(graph_str)

        for node in graph['nodes']:
            payload_pullspec = node['payload']
            payload_version = node['version']
            payload_key = f'{arch}:{payload_version}'

            if payload_key in rhcos_in_use:
                # We've already cached this payload RHCOS version
                print(f'Skipping {payload_key} since it is cached')
                continue

            print(f"Processing: {payload_version}  / {payload_pullspec}")
            for retry in (1, 2, 3, 4):
                release_json_result = oc.invoke('adm', cmd_args=['release', 'info', payload_pullspec, '-o=json'],
                                                no_namespace=True, auto_raise=False)
                if release_json_result.status() == 0:
                    break
                else:
                    print(f'Error acquiring image information: {release_json_result.err()}')

            if release_json_result.status() != 0:
                if '.ci' in payload_version or '.nightly' in payload_version:
                    continue
                else:
                    raise IOError(f'Unable to find RHCOS version for {payload_version}')

            release_info_str = release_json_result.out()
            release_info = json.loads(release_info_str)
            try:
                machine_os_rhcos_version = release_info['displayVersions']['machine-os']['Version']
            except KeyError:
                # No machine-os version information in the image. In old releases, use image info for the
                # machine-os-content image.
                print('  Querying for machine-os-content info')
                moc_pullspec = list(filter(lambda tag: tag['name'] == 'machine-os-content', release_info['references']['spec']['tags']))[0]['from']['name']
                if 'registry.svc' in moc_pullspec:
                    # Old CI registry. Nothing to be salvaged here.
                    print('  Old CI registry referenced. Skipping.')
                    continue
                print(f'  machine-os-content={moc_pullspec}')
                moc_image_info_json_result = oc.invoke('image', cmd_args=['info', moc_pullspec, '-o=json'],
                                                       no_namespace=True, auto_raise=True)
                machine_os_rhcos_version = json.loads(moc_image_info_json_result.out())['config']['config']['Labels']['version']

            print('  Querying for installer info')
            installer_pullspec = list(filter(lambda tag: tag['name'] == 'installer', release_info['references']['spec']['tags']))[0]['from']['name']
            if 'registry.svc' in installer_pullspec:
                # Old CI registry. Nothing to be salvaged here.
                print('  Old CI registry referenced. Skipping.')
                continue

            for retry in (1, 2, 3, 4):
                print(f'  installer={installer_pullspec}')
                try:
                    installer_image_info_json_result = oc.invoke('image', cmd_args=['info', installer_pullspec, '-o=json'],
                                                                 no_namespace=True, auto_raise=True)
                    installer_commit = json.loads(installer_image_info_json_result.out())['config']['config']['Labels']['io.openshift.build.commit.id']
                    break
                except:
                    print('  Error pulling reading installer image information')
                    if retry == 4:
                        raise

            print(f'  Processing installer commit: {installer_commit}')
            try:
                gitshow_process = subprocess.run(['git', '-C', str(installer_git_path), 'show', f'{installer_commit}:data/data/coreos/rhcos.json'], capture_output=True)
                gitshow_process.check_returncode()
            except:
                gitshow_process = subprocess.run(['git', '-C', str(installer_git_path), 'show', f'{installer_commit}:data/data/rhcos.json'], capture_output=True)
                gitshow_process.check_returncode()

            # Otherwise gitshow process contains a file like https://github.com/openshift/installer/blob/01adff5d629bb403a6cf49f9d44070762ef77e93/data/data/coreos/rhcos.json
            # or older format like https://github.com/openshift/installer/blob/bfdba2d19e3fa1105bab93aa4cce8bb7f44b4b2c/data/data/rhcos.json
            installer_rhcos_json = json.loads(gitshow_process.stdout)

            installer_ami_ids = dict()
            if 'amis' in installer_rhcos_json:
                # Older style without arch
                for region, region_entry in installer_rhcos_json['amis'].items():
                    installer_ami_ids[region] = {
                        'images': [region_entry['hvm']]
                    }
            else:
                for installer_arch_name, installer_arch in installer_rhcos_json['architectures'].items():
                    print(yaml.dump(installer_arch))
                    if 'images' in installer_arch['artifacts']:
                        images_list = installer_arch['artifacts']['images']
                    else:
                        images_list = installer_arch['images']
                    if 'aws' not in images_list:
                        print(f'  No AMIs for arch: {installer_arch_name}')
                        continue
                    for region_name, region_entry in images_list['aws']['regions'].items():
                        if region_name not in installer_ami_ids:
                            installer_ami_ids[region_name] = {}
                            installer_ami_ids[region_name]['images'] = []
                        installer_ami_ids[region_name]['images'].append(region_entry['image'])

            rhcos_in_use[payload_key] = {
                'payload_version': machine_os_rhcos_version,
                'installer_amis': installer_ami_ids
            }

            with riu_path.open('a+') as f:
                cache_entry = yaml.dump({
                    payload_key: rhcos_in_use[payload_key]
                })
                # Write section by section to cache file in case an error interrupts the full dump
                f.write(f'{cache_entry}\n')

    client = boto3.client('ec2')
    all_aws_regions = [region['RegionName'] for region in client.describe_regions()['Regions']]

    ignore_amis_younger_than = datetime.datetime.now() - datetime.timedelta(days=30)

    ami_analysis = dict()
    for aws_region in all_aws_regions:
        region_ami_analysis = dict()
        ami_analysis[aws_region] = region_ami_analysis

        # Ensure there are recycle bin rules setup to preserve AMI/snapshots
        rbin_client = boto3.client('rbin', region_name=aws_region)  # Recycle bin client
        for res_type in ('EBS_SNAPSHOT', 'EC2_IMAGE'):
            snapshot_rules = rbin_client.list_rules(ResourceType=res_type)
            if len(snapshot_rules['Rules']) == 0:
                # Create snapshot rule for X day retention
                print(f'Creating recycle bin rule for {res_type} in {aws_region}')
                create_recycle_bin_rule(rbin_client, res_type)

        region_client = boto3.client('ec2', region_name=aws_region)
        ec_resource = boto3.resource('ec2', region_name=aws_region)
        print(f'Querying for AMIs in {aws_region}..')
        images = region_client.describe_images(Owners=['self']).get('Images')

        for image in images:
            image_id = image['ImageId']
            image_name = image.get('Name', None)
            image_description = image.get('Description', None)
            image_creation = image['CreationDate']
            image_tags = image.get('Tags', [])
            image_tag_keys = [tag['Key'] for tag in image_tags]

            print(f'  Checking AMI {image_id} ({image_name})')

            if AMI_TAG_KEY_REFERENCED_BY in image_tag_keys:
                print(f'    AMI is labeled with {AMI_TAG_KEY_REFERENCED_BY}; preserving.')
                continue

            # Build up a string we are certain will contain the RHCOS version
            ami_info = f'{image_name} {image_description} {image_tags}'
            matches_payload_keys = list()
            for payload_key, payload_key_references in rhcos_in_use.items():
                if payload_key_references['payload_version'] in ami_info:
                    print(f'Will not clean up RHCOS AMI {image_id} ({image_name}) since it is referenced by a release controller release payload {payload_key}')
                    matches_payload_keys.append(payload_key)

                try:
                    region_list = payload_key_references['installer_amis'].get(aws_region, [])
                    if isinstance(region_list, dict):  # accommodate older cache file format
                        region_list = region_list['images']
                    if image_id in region_list:
                        print(f'Will not clean up RHCOS AMI {image_id} ({image_name}) since it is referenced by a release controller release payload installer commit for {payload_key}')
                        matches_payload_keys.append(payload_key)
                except:
                    print(yaml.dump(payload_key_references))
                    raise

                if matches_payload_keys and AMI_TAG_KEY_REFERENCED_BY not in image_tag_keys:
                    image_resource = ec_resource.Image(image_id)
                    image_resource.create_tags(
                        Tags=[
                            {
                                'Key': AMI_TAG_KEY_REFERENCED_BY,
                                'Value': ' '.join(matches_payload_keys)[:250]
                            },
                        ]
                    )
                    image_tag_keys.append(AMI_TAG_KEY_REFERENCED_BY)

            preserve_ami = len(matches_payload_keys) > 0

            creation_datetime = datetime.datetime.strptime(image_creation, "%Y-%m-%dT%H:%M:%S.%fZ")

            if creation_datetime > ignore_amis_younger_than:
                print(f'AMI {image_id} will be preserved due to recent creation')
                preserve_ami = True
                matches_payload_keys.append('AMI is recent')

            # Register pruning information for this image
            region_ami_analysis[image_id] = {
                'name': image_name,
                'description': image_description,
                'creation': image_creation,
                'tags': image_tags,
                'preserve': preserve_ami,
                'used_by_payloads': matches_payload_keys,
            }

            if not preserve_ami:
                # No payload matches this RHCOS version. Find EBS snapshots to delete.
                ebs_snapshots = list()
                for block_device_mapping in image['BlockDeviceMappings']:
                    if 'Ebs' in block_device_mapping and 'SnapshotId' in block_device_mapping['Ebs']:
                        snapshot_id = block_device_mapping['Ebs']['SnapshotId']
                        ebs_snapshots.append(snapshot_id)

                region_ami_analysis[image_id]['snapshots'] = ebs_snapshots

                if AMI_TAG_KEY_GARBAGE_COLLECT not in image_tag_keys:
                    image_resource = ec_resource.Image(image_id)
                    image_resource.create_tags(
                        Tags=[
                            {
                                'Key': AMI_TAG_KEY_GARBAGE_COLLECT,
                                'Value': 'true'
                            },
                        ]
                    )
                    print(f'labeled {image_id} in {aws_region}')

            print(f'Assessed: {image_id}')
            print(yaml.dump(region_ami_analysis[image_id]))

    analysis = pathlib.Path('analysis.yaml')
    analysis.write_text(yaml.dump(ami_analysis))
