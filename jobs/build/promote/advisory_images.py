#!/usr/bin/python
# -*- coding: utf8 -*-
'''
Created on Oct 19, 2016
@author: zhizhang@redhat.com
'''


from bs4 import BeautifulSoup
import getpass
import urllib2
import socket
import re
import base64
import ssl


major = raw_input("Please enter the OpenShift major version (3 or 4): ")
if major not in ['3', '4']:
    print "You must choose OCP 3 or 4."
    exit(1)
advisory = raw_input("Please enter the image advisory number (number): ")
if advisory == '' or not advisory.isdigit():
    print "You must enter a numeric advisory."
    exit(1)
user_name = raw_input("Please input your kerberos username: ")
if user_name == '':
    print "You must enter a username with access to erratatool."
    exit(1)
password = getpass.getpass("Please input your kerberos passwd: ")
if password == '':
    print "You must enter a password for this user."
    exit(1)


image_prefix = 'openshift' + major + '/'
repo_prefix = 'redhat-openshift' + major + '-'
link = 'https://errata.devel.redhat.com/errata/content/' + advisory
print 'advisory content link is :', link
print 'user_name is :', user_name


context = ssl._create_unverified_context()
request = urllib2.Request(link)
base64string = base64.encodestring('%s:%s' % (user_name, password)).replace('\n', '')
request.add_header("Authorization", "Basic %s" % base64string)
response = urllib2.urlopen(request, context=context)
html_data = response.read()
soup = BeautifulSoup(html_data)


print 'start to analyze---------------'
first_part=soup.find("table", {"class": "bug_list content_list"}).find_all(class_='bz_even')
second_part=soup.find("table", {"class": "bug_list content_list"}).find_all(class_='bz_odd')
print '#########'
for item in first_part:
    first = item.td.a.contents[0]
    second = item.findAll(class_='toggle-files dist_name')[0].contents[0].replace(repo_prefix, '')
    pattern = re.compile(r'-(v|[0-9])+[^a-z]*$')
    mach_for2 = pattern.search(first)
    if mach_for2:
        final = image_prefix + second + ":" + mach_for2.group().lstrip()[1:]
        print str(final).replace(" ", "")
    else:
        print 'This line does not look right:', first
for item in second_part:
    first = item.td.a.contents[0]
    second = item.findAll(class_='toggle-files dist_name')[0].contents[0].replace(repo_prefix,'')
    pattern = re.compile(r'-(v|[0-9])+[^a-z]*$')
    mach_for2 = pattern.search(first)
    if mach_for2:
        final = image_prefix + second + ":" + mach_for2.group().lstrip()[1:]
        print str(final).replace(" ", "")
    else:
        print 'This line does not look right:', first
print '############'
