Role Name
=========

Establishes a systemd unit which will run on AWS instances of this AMI
before atomic-openshift-node starts. The unit will periodically pull 
a docker config.json secret from the master and update the local 
.docker/config.json secrets on the host.

Pulls secret from secrets/reg-aws-dockercfg (openshift namespace).

This mechanism is designed to prevent the need to bake authenticated
registry credentials into the AMI.

Requirements
------------


Role Variables
--------------

Dependencies
------------


Example Playbook
----------------

License
-------

Apache 2.0

Author Information
------------------
