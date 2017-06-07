#!/usr/bin/python

# This script is designed to run on an openshift master and output a JSON
# message to stdout including details about the installed software.
# The message can be sent out on the Red Hat CI message bus in order
# to inform QE of an upgrade.

import subprocess
import sys
import json

if len(sys.argv) != 2:
    print "Invalid syntax; cluster name required"
    sys.exit(1)

if sys.argv[0] != "-":
    print "Invocation is no longer as stdin to python app; assumptions have changed so exiting."
    sys.exit(1)

cluster_name = sys.argv[1]

if cluster_name == "test-key":
    oc_v = """
oc v3.5.5.19
kubernetes v1.5.2+43a9be4
features: Basic-Auth GSSAPI Kerberos SPNEGO

Server https://internal.api.free-int.openshift.com:443
openshift v3.5.5.19
kubernetes v1.5.2+43a9be4
"""
else:
    oc_v = str(subprocess.check_output(["oc", "version"])).strip()

oc_version = None
oc_version_prefix = "oc v"

kubernetes_version = None
kubernetes_version_prefix = "kubernetes v"

for line in oc_v.split("\n"):
        line = line.strip()
        if oc_version is None and line.startswith(oc_version_prefix):
                oc_version = line[len(oc_version_prefix):]
        if kubernetes_version is None and line.startswith(kubernetes_version_prefix):
                kubernetes_version = line[len(kubernetes_version_prefix):]


major, minor = oc_version.split(".")[:2]
oc_short_version = "%s.%s" % (major,minor)

if cluster_name == "test-key":
    docker_version = "1.12.6-16.el7"
else:
    docker_version = subprocess.check_output(["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "docker"])

online_version = None
try:
        online_version = subprocess.check_output(["rpm", "-q", "--qf", "%{VERSION}", "openshift-scripts-free"])
except:
        pass

try:
        online_version = subprocess.check_output(["rpm", "-q", "--qf", "%{VERSION}", "openshift-scripts-devpreview"])
except:
        pass

msg = {
    "owner": "Continuous Delivery",
    "email": "jupierce@redhat.com",
    "CI_TYPE": "component-build-done",
    "destination": "/topic/CI",
    "product": "OSO",
    "cluster name": cluster_name,
    "description": "OSO cluster upgraded",
    "version": oc_version,
    "short_version": oc_short_version,
    "oc_version": oc_version,
    "online_version": online_version,
    "docker_version": docker_version,
    "api_url": "https://api." + cluster_name + ".openshift.com",
    "console_url": "https://console." + cluster_name + ".openshift.com/console",
}

print json.dumps(msg)
