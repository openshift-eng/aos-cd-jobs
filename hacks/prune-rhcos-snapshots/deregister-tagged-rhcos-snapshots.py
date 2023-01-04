#!/usr/bin/env python3
import os
import re

import boto3
import openshift as oc
import re
import json
import yaml
from typing import Dict, List, Set
import datetime
import urllib3
import pathlib
import subprocess

# Set to "true" if an AMI is selected for garbage collection
AMI_TAG_KEY_GARBAGE_COLLECT = 'garbage_collect'

# Set to "true" if an AMI is mentioned in installer reference
AMI_TAG_KEY_PRODUCTION = 'production'

AmiId = str

if __name__ == '__main__':

    client = boto3.client('ec2')
    all_aws_regions = [region['RegionName'] for region in client.describe_regions()['Regions']]

    production_count = 0
    gc_count = 0
    for aws_region in all_aws_regions:
        print(f'Processing {aws_region}')

        region_client = boto3.client('ec2', region_name=aws_region)
        ec_resource = boto3.resource('ec2', region_name=aws_region)
        print(f'Querying for AMIs in {aws_region}..')

        impossible_images = region_client.describe_images(
            Owners=['self'],
            Filters=[
                {
                    'Name': f'tag:{AMI_TAG_KEY_GARBAGE_COLLECT}',
                    'Values': [
                        'true'
                    ]
                },
                {
                    'Name': f'tag-key',
                    'Values': [
                        AMI_TAG_KEY_PRODUCTION
                    ]
                }
            ]
        ).get('Images')

        if len(list(impossible_images)) > 0:
            print(f'Found production images tagged with {AMI_TAG_KEY_GARBAGE_COLLECT}. Correct this before proceeding.')
            exit(1)

        gc_images = list(region_client.describe_images(
            Owners=['self'],
            Filters=[
                {
                    'Name': f'tag:{AMI_TAG_KEY_GARBAGE_COLLECT}',
                    'Values': [
                        'true'
                    ]
                },
            ]
        ).get('Images'))

        production_images = list(region_client.describe_images(
            Owners=['self'],
            Filters=[
                {
                    'Name': f'tag-key',
                    'Values': [
                        AMI_TAG_KEY_PRODUCTION
                    ]
                }
            ]
        ).get('Images'))

        if len(production_images) == 0 and len(gc_images) > 0:
            print(f'Found NO production images tagged with {AMI_TAG_KEY_PRODUCTION} in but did find images to garbage collect. Correct this oddity before proceeding.')
            exit(1)

        production_count += len(production_images)
        gc_count += len(gc_images)

        ebs_snapshot_ids = set()

        print(f'Planning to deregister {len(gc_images)} AMIs from {aws_region}')
        for image in gc_images:
            image_id = image['ImageId']
            image_resource = ec_resource.Image(image_id)

            for block_device_mapping in image['BlockDeviceMappings']:
                if 'Ebs' in block_device_mapping and 'SnapshotId' in block_device_mapping['Ebs']:
                    snapshot_id = block_device_mapping['Ebs']['SnapshotId']
                    # Snapshots cannot be deleted until the image(s) referencing them have been deregistered
                    ebs_snapshot_ids.add(snapshot_id)

            image_resource.deregister()
            print(f'Deregistered: {image_id}')

        # delete referenced snapshots
        for snapshot_id in ebs_snapshot_ids:
            snapshot = ec_resource.Snapshot(snapshot_id)
            snapshot.delete()
            print(f'Deleted snapshot: {snapshot_id}')

    print(f'Saved {production_count} images.')
    print(f'Deregistered {gc_count} images.')
