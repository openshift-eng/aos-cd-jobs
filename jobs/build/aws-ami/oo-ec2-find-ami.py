#!/usr/bin/env python
""" Script to help find AWS AMI's based on tags """
from __future__ import print_function
# vim: expandtab:tabstop=4:shiftwidth=4
# Ignoring module name
# pylint: disable=invalid-name

import argparse
import boto3

class OOEC2FindAMI(object):
    """ Class to query for AMI's """

    def __init__(self):
        """ This is the init function """

        self.args = None
        self.amis = None
        self.region = None
        self.ec2 = None
        self.query_filter = []
        self.ami_tags = {}
        self.ami_name = None

    def parse_tags(self, incoming_tag):
        """ Add self.ami_tags from the cli argparser

            Tags come in from argparse in the form of 'key=value'. This function will
             validate this, and add the tags to self.ami_tags so they can be used
             later on to filter on
        """

        if incoming_tag.count('=') < 0 or incoming_tag.count('=') > 1:
            msg = "Tags are expected to be in the format of 'key=value', found: %r" % incoming_tag
            raise argparse.ArgumentTypeError(msg)

        split_tag = incoming_tag.split('=')
        self.ami_tags[split_tag[0]] = split_tag[1]

    def parse_args(self):
        """ parse the args from the cli """

        parser = argparse.ArgumentParser(description='EC2 Copy AMI to All Regions')

        parser.add_argument('-n', '--name', help='The AMI Name to search for')

        parser.add_argument('-r', '--region', default='us-east-1', required=False,
                            help='The region the AMI to be copied is located. Default: us-east-1')

        parser.add_argument('-t', '--tags', default=None, type=self.parse_tags,
                            help='AMI Tags to search for; maybe be used multiple times.\
                                  example: operating_system=RedHat')

        parser.add_argument('-v', '--verbose', action='store_true', help='Increase verbosity in the output')

        parser.add_argument('--show-all', default=False, action='store_true', help='Return all AMIs found')

        self.args = parser.parse_args()
        self.region = self.args.region
        self.ami_name = self.args.name

    def build_filter(self):
        """ Build the filter to pass to EC2 """

        for k, v in self.ami_tags.iteritems():
            tag_dict = {'Name': 'tag:' + k,
                        'Values': [v]}
            self.query_filter.append(tag_dict)

        if self.ami_name:
            tag_dict = {'Name': 'name',
                        'Values': [self.ami_name]}
            self.query_filter.append(tag_dict)

    def get_images(self):
        """ Query AMI copy the ami to all regions """

        self.amis = self.ec2.describe_images(Filters=self.query_filter, Owners=['self'])['Images']

        # sort the amis by creation date
        self.amis.sort(key=lambda x: x['CreationDate'])


    def print_amis(self):
        """ print the ami info to screen """

        if self.args.show_all:
            for ami in self.amis:
                if self.args.verbose:
                    print("id: {}, name: {}, create_date: {}".format(ami['ImageId'], ami['Name'], ami['CreationDate']))
                else:
                    print(ami['ImageId'])
        else:

            if self.args.verbose:
                print("id: {}, name: {}, create_date: {}".format(self.amis[-1]['ImageId'], self.amis[-1]['Name'],
                                                                 self.amis[-1]['CreationDate']))
            else:
                print(self.amis[-1]['ImageId'])

    def main(self):
        """ main function """

        self.parse_args()
        self.ec2 = boto3.client('ec2', region_name=self.region)
        self.build_filter()
        self.get_images()
        self.print_amis()

if __name__ == "__main__":
    OOEFA = OOEC2FindAMI()
    OOEFA.main()
