import sys
import yaml

# process data from stdin pipe
# data should come from following command
# doozer --group=openshift-4.1 images:print --label 'com.redhat.delivery.appregistry' --short '{label},{name},{build},{version}' | tee appreg.list
result = []
with open(sys.argv[1], 'r') as f_in:
    for line in f_in.readlines():
        status, name, nvr, version = line.strip().split(',')
        if status.lower() == 'true':
            result.append({'name': name,
                           'nvr': nvr,
                           'version': version.replace('v', '')
                           })

with open(sys.argv[2], 'w') as f:
    f.write(yaml.safe_dump(result, indent=2, default_flow_style=False))
